from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
import shutil
import subprocess
from github import Github
from dotenv import load_dotenv
import openai
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

app = FastAPI()

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Environment Variables
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


#client = openai.OpenAI(api_key=OPENAI_API_KEY)
client = openai.OpenAI(api_key=OPENAI_API_KEY)

BASE_DIR = "repos"

# Initialize GitHub and OpenAI clients
g = Github(GITHUB_TOKEN)
openai.api_key = OPENAI_API_KEY

# Serve static files (for HTML UI)
app.mount("/static", StaticFiles(directory="static"), name="static")

class RepoRequest(BaseModel):
    repo_url: str
    branch: str

class AIRequest(BaseModel):
    repo_name: str
    file_path: str
    improvement_type: str  # "bug_fix", "performance", "cleanup"

class CommitRequest(BaseModel):
    repo_name: str
    file_path: str
    commit_message: str

@app.post("/clone_repo/")
def clone_repo(request: RepoRequest):
    repo_name = request.repo_url.split('/')[-1]
    repo_path = os.path.join(BASE_DIR, repo_name)
    
    if os.path.exists(repo_path):
        shutil.rmtree(repo_path)  # Remove old repo if exists
    
    clone_cmd = ["git", "clone", "--branch", request.branch, request.repo_url, repo_path]
    result = subprocess.run(clone_cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        raise HTTPException(status_code=400, detail=f"Error cloning repo: {result.stderr}")
    
    return {"message": "Repo cloned successfully", "repo_name": repo_name}

@app.get("/list_repos/")
def list_repos():
    repos = [d for d in os.listdir(BASE_DIR) if os.path.isdir(os.path.join(BASE_DIR, d))]
    return {"repos": repos}

@app.get("/list_files/{repo_name}")
def list_files(repo_name: str):
    repo_path = os.path.join(BASE_DIR, repo_name)
    if not os.path.exists(repo_path):
        raise HTTPException(status_code=404, detail="Repository not found")
    
    file_list = []
    for root, _, files in os.walk(repo_path):
        for file in files:
            if file.endswith(".py"):
                file_list.append(os.path.relpath(os.path.join(root, file), repo_path))
    
    return {"files": file_list}

@app.post("/improve_code/")
def improve_code(request: AIRequest):
    repo_path = os.path.join(BASE_DIR, request.repo_name)
    file_path = os.path.join(repo_path, request.file_path)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    with open(file_path, "r") as f:
        code = f.read()
    
    prompt = f"Improve the following Python code with {request.improvement_type} improvements:\n\n{code}"  
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "system", "content": "You are an expert software engineer."},
                  {"role": "user", "content": prompt}],
        max_tokens=1000
    )


    improved_code = response.choices[0].message.content  
    
    with open(file_path, "w") as f:
        f.write(improved_code)
    
    return {"message": "Code improved successfully", "file_path": request.file_path}

@app.post("/commit_changes/")
def commit_changes(request: CommitRequest):
    repo_path = os.path.join(BASE_DIR, request.repo_name)
    file_path = os.path.join(repo_path, request.file_path)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    commit_cmds = [
        ["git", "-C", repo_path, "add", request.file_path],
        ["git", "-C", repo_path, "commit", "-m", request.commit_message],
        ["git", "-C", repo_path, "push"]
    ]
    
    for cmd in commit_cmds:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise HTTPException(status_code=400, detail=f"Error committing changes: {result.stderr}")
    
    return {"message": "Changes committed successfully", "file_path": request.file_path}

@app.get("/")
def serve_html():
    return RedirectResponse(url="/static/index.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
