"""FastAPI application for exporting Cync device configuration from the Cync Cloud API."""

import logging
import os
import sys
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from cync_lan.cloud_api import CyncCloudAPI
from cync_lan.const import *


logger = logging.getLogger("cync-lan.exporter")
formatter = logging.Formatter(
    "%(asctime)s.%(msecs)d %(levelname)s [%(module)s:%(lineno)d] > %(message)s",
    "%m/%d/%y %H:%M:%S",
)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO if CYNC_DEBUG is False else logging.DEBUG)
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO if CYNC_DEBUG is False else logging.DEBUG)

cync_cloud_api: Optional[CyncCloudAPI] = None

class OTPRequest(BaseModel):
    otp: int

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Or set to your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=Path(CYNC_STATIC_DIR).expanduser().resolve()), name="static")

@app.get("/exporter", response_class=HTMLResponse)
async def get_index():
    global cync_cloud_api
    if cync_cloud_api is None:
        cync_cloud_api = CyncCloudAPI()

    with Path(CYNC_STATIC_DIR + "/index.html").expanduser().resolve().open("r") as f:
        return f.read()

@app.get("/api/export/start")
async def start_export():
    ret_msg = "Export started successfully"
    try:
        succ = await cync_cloud_api.check_token()
        if succ is False:
            req_succ = await cync_cloud_api.request_otp()
            if req_succ is True:
                ret_msg = "OTP requested, check your email for the OTP code to complete the export."
                return {"success": False, "message": ret_msg}
            else:
                ret_msg = "Failed to request OTP. Please check your credentials or network connection."
                return {"success": False, "message": ret_msg}
        else:
            await cync_cloud_api.export_config_file()
            return {"success": True, "message": ret_msg}
    except Exception as e:
        logger.exception(f"Export start failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/export/otp")
async def submit_otp(otp_request: OTPRequest):
    try:
        succ = await cync_cloud_api.send_otp(otp_request.otp)
        return {"success": succ, "message": "Export completed" if succ else "Failed to complete export"}
    except Exception as e:
        logger.exception(f"Export completion failed: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/healthcheck")
async def health_check():
    """Health check endpoint to verify if the server is running."""
    return {"status": "ok", "message": "Cync Export Server is running"}

@app.get("/api/export/download")
async def download_config():
    config_path = CYNC_CONFIG_FILE_PATH
    if os.path.exists(config_path):
        return FileResponse(config_path, filename="cync_mesh.yaml")
    raise HTTPException(status_code=404, detail="Config file not found")

class ExportServer:
    lp = "ExportServer:"
    _instance: Optional['ExportServer'] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        self.app = app
        self.uvi_server = uvicorn.Server(
            config=uvicorn.Config(app, host=CYNC_SRV_HOST, port=INGRESS_PORT, log_level="info")
        )

    async def start(self):
        """Start the FastAPI server."""
        lp = f"{self.lp}start:"
        logger.info(f"{lp} Starting FastAPI export server on {CYNC_SRV_HOST}:{INGRESS_PORT}")
        await self.uvi_server.serve()

    async def stop(self):
        """Stop the FastAPI server."""
        lp = f"{self.lp}stop:"
        logger.info(f"{lp} Stopping FastAPI export server...")
        await self.uvi_server.shutdown()
