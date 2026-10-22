"""Local-only API and frontend. Start with python app.py."""
import os
import secrets
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import uvicorn
import butler
import readers

app = FastAPI(title='Lazy File Butler', docs_url=None, redoc_url=None)
TOKEN = secrets.token_urlsafe(32)


@app.middleware('http')
async def local_only(request: Request, call_next):
    if request.url.hostname not in {'localhost', '127.0.0.1'}:
        return JSONResponse({'detail': 'Use localhost to open this app.'}, status_code=403)
    if request.method != 'GET':
        origin = request.headers.get('origin')
        if origin and origin not in {'http://localhost:8002', 'http://127.0.0.1:8002'}:
            return JSONResponse({'detail': 'Cross-origin requests are blocked.'}, status_code=403)
        if request.headers.get('x-butler-token') != TOKEN:
            return JSONResponse({'detail': 'Refresh this page to reconnect to Butler.'}, status_code=403)
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'"
    return response


@app.exception_handler(ValueError)
async def invalid(request, error):
    return JSONResponse({'detail': str(error)}, status_code=400)


class Analyze(BaseModel):
    root: str
    recursive: bool = False
    model: str


class Edit(BaseModel):
    id: str
    name: str = Field(min_length=1, max_length=200)
    category: str


class Apply(BaseModel):
    edits: list[Edit] = Field(max_length=100)


@app.get('/api/bootstrap')
def bootstrap():
    return {'token': TOKEN, 'categories': butler.CATEGORIES, 'model': butler.model_status(), 'shortcuts': {name: str(Path.home()/name) for name in ['Desktop','Downloads','Documents'] if (Path.home()/name).is_dir()}}


@app.get('/api/active')
def active():
    return {'id': next((key for key, job in list(butler.JOBS.items()) if job['state']=='running'), None)}


@app.get('/api/models')
def models():
    return butler.model_status()


class Browse(BaseModel):
    path: str = ''


@app.post('/api/folders')
def folders(data: Browse):
    p = Path(data.path).expanduser() if data.path else Path.home()
    if not p.is_absolute() or p.is_symlink() or not p.is_dir():
        raise ValueError('That folder is unavailable. Try its parent folder.')
    p = p.resolve()
    try:
        entries = sorted((item for item in p.iterdir() if not item.name.startswith('.') and not item.is_symlink() and item.is_dir()), key=lambda item:item.name.casefold())
        return {'path': str(p), 'parent': str(p.parent) if p.parent != p else None,
                'selectable': p not in (Path('/'), Path.home()),
                'folders': [{'name': item.name, 'path': str(item)} for item in entries[:300]]}
    except PermissionError:
        raise ValueError('macOS denied access. Allow the running Terminal or Python app access in System Settings, or choose another folder.')


@app.post('/api/jobs/{key}/cancel')
def cancel(key: str):
    job = butler.JOBS.get(key)
    if not job:
        raise ValueError('This scan is no longer active.')
    job['cancel_requested'] = True
    return {'ok': True}


@app.post('/api/demo')
def demo():
    return {'root': butler.demo_folder()}


@app.post('/api/analyze')
def analyze(data: Analyze):
    return butler.start_analysis(data.root, data.recursive, data.model)


@app.get('/api/jobs/{key}')
def job(key: str):
    if key in butler.JOBS and butler.JOBS[key]['state'] not in {'done'}:
        return butler.JOBS[key]
    try:
        return {'id': key, 'state': 'done', 'plan': butler.get('plans', key)}
    except ValueError:
        raise HTTPException(404, 'This analysis was interrupted. Analyze the folder again; no files were moved.')


@app.post('/api/plans/{key}/apply')
def apply(key: str, data: Apply):
    return butler.apply_plan(key, [edit.model_dump() for edit in data.edits])


@app.get('/api/history')
def history():
    return butler.history()


@app.post('/api/history/{key}/undo')
def undo(key: str):
    return butler.undo(key)


@app.get('/')
def index():
    return FileResponse(Path(__file__).parent/'static'/'index.html')


app.mount('/static', StaticFiles(directory=Path(__file__).parent/'static'), name='static')

if __name__ == '__main__':
    readers.prepare_native()
    uvicorn.run(app, host='127.0.0.1', port=8002)
