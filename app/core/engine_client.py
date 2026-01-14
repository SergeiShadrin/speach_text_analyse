import requests
from pathlib import Path
from datetime import date
from typing import Optional, Union, List, Dict
from app.core.config import settings

class ResearchEngineClient:

    def __init__(self):
        # Fallback to localhost if not in settings
        self.api_url = settings.RESEARCH_ENGINE_URL

    def is_online(self) -> bool:
        """Check if the API is reachable."""
        try: 
            requests.get(f"{self.api_url}/", timeout=1)
            return True
        except requests.ConnectionError:
            return False
        
    def file_exists(self, filename: str, project_name: str = settings.DEFAULT_PROJECT_NAME) -> bool:
        """Check if a file exists in the project (by name)."""
        try:
            params = {"q": filename}
            response = requests.get(f"{self.api_url}/{project_name}/files", params=params)
            if response.status_code == 200:
                files = response.json()
                for f in files:
                    if f['name'] == filename:
                        return True
            return False
        except requests.RequestException:
            return False
            
    def list_files(self, 
                   project_name: str = settings.DEFAULT_PROJECT_NAME, 
                   q: Optional[str] = None,
                   date_from: Optional[Union[date, str]] = None) -> List[Dict]:
        """
        Lists files in a specific project.
        - q: Search text (Filename, Description, Event)
        - date_from: Filter by Event Date (YYYY-MM-DD or date object)
        """
        params = {}
        if q:
            params["q"] = q

        if date_from:
            params["date"] = str(date_from) 

        try: 
            url = f"{self.api_url}/{project_name}/files"
            response = requests.get(url, params=params)
            
            response.raise_for_status()
            
            return response.json()

        except requests.exceptions.RequestException as e:
            print(f"API Request Failed: {e}")
            return []  # Return empty list on failure
            

    def get_file_details(self, file_id: str) -> Optional[Dict]:
        """
        Returns full details (text, metadata, events) of a file.
        """
        if not file_id:
            print("Error: No file_id provided.")
            return None

        try:
            url = f"{self.api_url}/files/{file_id}"
            response = requests.get(url)
            response.raise_for_status()

            return response.json()
        
        except requests.exceptions.RequestException as e:
            print(f"API Request Failed: {e}")
            return None
            

    def search_and_download(self, 
                        search_query: Optional[str] = None,
                        project_name: str = settings.DEFAULT_PROJECT_NAME, 
                        date_from: Optional[Union[date, str]] = None,
                        output_dir: Union[str, Path] = settings.DEFAULT_OUTPUT_FOLDER) -> Optional[str]:
        """
        Downloads a ZIP file from the API based on filters.
        """
        # 1. Construct URL
        url = f"{self.api_url}/{project_name}/download-zip"

        # 2. Prepare Params (Must match main.py endpoints)
        params = {}
        if search_query:
            params["search_query"] = search_query
        
        # ✅ NEW: Add Date parameter
        if date_from:
            params["date"] = str(date_from)

        try:
            print(f"⬇️  Requesting: {url} | Params: {params}")
            
            # 3. Stream Request
            with requests.get(url, params=params, stream=True) as response:
                response.raise_for_status()

                # 4. Get Filename from Header or Fallback
                if "content-disposition" in response.headers:
                    content_disposition = response.headers["content-disposition"]
                    filename = content_disposition.split("filename=")[-1].strip('"')
                else:
                    filename = f"{project_name}_download.zip"

                # 5. Save to Disk
                output_path = Path(output_dir)
                output_path.mkdir(parents=True, exist_ok=True)
                final_path = output_path / filename
                
                with open(final_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                print(f"✅ Success! File saved to: {final_path}")
                return str(final_path)
        
        except requests.exceptions.RequestException as e:
            print(f"❌ API Request Failed: {e}")
            return None
            

    def delete_file(self, file_id: str) -> bool:
        """
        Permanently delete a file.
        """
        if not file_id:
            print("❌ Error: No file_id provided.")
            return False

        url = f"{self.api_url}/files/{file_id}"

        try:
            response = requests.delete(url)
            response.raise_for_status()
            
            print(f"✅ File {file_id} deleted successfully.")
            return True

        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to delete file: {e}")
            return False