"""FastAPI application for exporting Cync device configuration from the Cync Cloud API."""

import os
import logging
import sys

from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import CyncLAN


app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

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

cync_lan = CyncLAN()


class AuthRequest(BaseModel):
    email: str
    password: str

class OTPRequest(BaseModel):
    otp: str

# Store export state temporarily (in-memory, not persistent)
export_state = {}

@app.get("/", response_class=HTMLResponse)
async def get_index():
    with open("static/index.html", "r") as f:
        return f.read()

@app.post("/api/export/start")
async def start_export(auth: AuthRequest):
    try:
        # Call the cync-lan export function to initiate authentication
        # Assumes cync_lan.export returns a session ID or token for OTP
        session_id = await cync_lan.start_device_export(auth.email, auth.password)
        export_state[auth.email] = {"session_id": session_id}
        return {"status": "success", "message": "OTP sent to email"}
    except Exception as e:
        logger.error(f"Export start failed: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/export/otp")
async def submit_otp(otp_request: OTPRequest, email: str = Form(...)):
    try:
        if email not in export_state:
            raise HTTPException(status_code=400, detail="No active export session")
        session_id = export_state[email]["session_id"]
        # Complete export with OTP and save cync_mesh.yaml
        config_path = "/root/cync-lan/config/cync_mesh.yaml"
        await cync_lan.complete_export(session_id, otp_request.otp, config_path)
        del export_state[email]  # Clear session
        return {"status": "success", "message": "Export completed", "config_path": config_path}
    except Exception as e:
        logger.error(f"Export completion failed: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/export/download")
async def download_config():
    config_path = "/root/cync-lan/config/cync_mesh.yaml"
    if os.path.exists(config_path):
        return FileResponse(config_path, filename="cync_mesh.yaml")
    raise HTTPException(status_code=404, detail="Config file not found")

class ExportServer:
    def __init__(self):
        self.app = app

    async def start(self):
        """Start the FastAPI server."""
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=8099)
