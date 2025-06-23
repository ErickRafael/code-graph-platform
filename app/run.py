#!/usr/bin/env python3
"""Application runner for the CAD Graph Platform."""

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)