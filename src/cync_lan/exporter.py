"""FastAPI application for exporting Cync device configuration from the Cync Cloud API."""

import logging
import os
import sys

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .cloud_api import CyncCloudAPI
from .const import *


logger = logging.getLogger("cync-lan.exporter")
formatter = logging.Formatter(
    "%(asctime)s.%(msecs)d %(levelname)s [%(module)s:%(lineno)d] > %(message)s",
    "%m/%d/%y %H:%M:%S",
)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

class OTPRequest(BaseModel):
    otp: int

cync_cloud_api = CyncCloudAPI()
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def get_index():
    with open("static/index.html", "r") as f:
        return f.read()

@app.get("/api/export/start")
async def start_export():
    ret_msg = "Export started successfully"
    try:
        # check token, if it returns true, the access token is valid
        # if false, we need to request an OTP from Cync Cloud API
        succ = await cync_cloud_api.check_token()
        if succ is False:
            req_succ = await cync_cloud_api.request_otp()
            if req_succ is True:
                ret_msg = "OTP requested, check your email for the OTP code to complete the export."
            else:
                ret_msg = "Failed to request OTP. Please check your credentials or network connection."
        else:
            await cync_cloud_api.export_config_file()
        return {"status": "success", "message": ret_msg}
    except Exception as e:
        logger.error(f"Export start failed: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/export/otp")
async def submit_otp(otp_request: OTPRequest):
    try:
        await cync_cloud_api.send_otp(otp_request.otp)
        return {"status": "success", "message": "Export completed"}
    except Exception as e:
        logger.error(f"Export completion failed: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/export/download")
async def download_config():
    config_path = CYNC_CONFIG_FILE_PATH
    if os.path.exists(config_path):
        return FileResponse(config_path, filename="cync_mesh.yaml")
    raise HTTPException(status_code=404, detail="Config file not found")

class ExportServer:
    def __init__(self):
        self.app = app
        self.uvi_server = uvicorn.Server(
            config=uvicorn.Config(app, host="0.0.0.0", port=CYNC_PORT - 1, log_level="info")
        )

    async def start(self):
        """Start the FastAPI server."""
        self.uvi_server.run()

    async def stop(self):
        """Stop the FastAPI server."""
        # This is a placeholder for any cleanup logic if needed
        await self.uvi_server.shutdown()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logger.info("Starting Cync LAN Exporter...")
    server = ExportServer()
    try:
        import asyncio
        asyncio.run(server.start())
    except KeyboardInterrupt:
        logger.info("Stopping Cync LAN Exporter...")
        asyncio.run(server.stop())
    except Exception as e:
        logger.error(f"An error occurred: {e}", exc_info=True)
