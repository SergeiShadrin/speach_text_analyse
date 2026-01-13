import requests
from app.core.config import settings
from pathlib import Path


class ResearchEngineClient:

    def __init__(self):
        # Fallback to localhost if not in settings
        self.api_url = settings.RESEARCH_ENGINE_URL

    def is_online(self) -> bool:
        try: 
            requests.get(f"{self.api_url}/", timeout=1)
            return True
        except requests.ConnectionError:
            return False
        
    def file_exists(self, filename: str, project_name: str = "Transcriptions") -> bool:
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
            
    # search of the transcription files 
    def list_files(self, project_name: str = "Transcriptions", q: str = None):
            """
            Lists files in a specific project via the API with a research query.
            To use to visualise the list of found files. 
            """
            params = {}
            if q:
                params["q"] = q

            try: 
                # 2. Construct the request
                url = f"{self.api_url}/{project_name}/files"
                response = requests.get(url, params=params)
                
                # 3. Check for HTTP errors (404, 500, etc.)
                response.raise_for_status()
                
                return response.json()

            except requests.exceptions.RequestException as e:
                # 4. Log the error or handle it gracefully
                print(f"API Request Failed: {e}")
                return []  # Return an empty list so your UI doesn't crash
            

    def get_file_details(self, file_id: str):  # Fixed typo: 'detailes' -> 'details'
            """
            Returns the full details of a file, including the transcription text.
            """
            # 1. FIX: Handle missing ID immediately
            if not file_id:
                print("Error: No file_id provided.")
                return None

            try:
                url = f"{self.api_url}/files/{file_id}"
                response = requests.get(url)
                response.raise_for_status()

                return response.json() # Returns a Dict (Object)
            
            except requests.exceptions.RequestException as e:
                print(f"API Request Failed: {e}")
                # 2. FIX: Return None, not [], for a single item
                # Your API returns a Dictionary (one file), not a List. 
                # If you return [], code like 'result.get("filename")' will crash later.
                return None
            


    def search_and_download(self, 
                        search_query: str,
                        project_name: str = "Global_Search", 
                        output_dir: str = "/Users/sergeishadrin/Downloads"):
            """
            Downloads a ZIP file from the API and saves it to your local disk.
            """
            # 1. FIX URL: Use the API URL + the endpoint structure
            # The API expects: /<project_name>/download-zip
            url = f"{self.api_url}/{project_name}/download-zip"

            # 2. FIX PARAMS: search_query goes here, NOT in the URL
            # output_dir does NOT go here (the server doesn't care where you save it)
            params = {}
            if search_query:
                params["search_query"] = search_query

            try:
                # 3. FIX REQUEST: Use stream=True for large files
                print(f"Requesting: {url} with params {params}")
                with requests.get(url, params=params, stream=True) as response:
                    response.raise_for_status()

                    # 4. GET FILENAME: Try to get the filename from the server headers
                    # If not provided, fallback to a default name
                    if "content-disposition" in response.headers:
                        content_disposition = response.headers["content-disposition"]
                        filename = content_disposition.split("filename=")[-1].strip('"')
                    else:
                        filename = f"{project_name}_download.zip"

                    # 5. FIX SAVING: Write the binary data to your local disk
                    target_path = Path(output_dir) / filename
                    
                    # Ensure the directory exists
                    target_path.parent.mkdir(parents=True, exist_ok=True)

                    with open(target_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                    
                    print(f"✅ Success! File saved to: {target_path}")
                    return str(target_path)
            
            except requests.exceptions.RequestException as e:
                print(f"❌ API Request Failed: {e}")
                return None
            
        

    def delete_file(self, file_id: str) -> bool:
        """
        Sends a request to permanently delete a file by its ID.
        Returns True if successful, False otherwise.
        """
        # Safety check
        if not file_id:
            print("❌ Error: No file_id provided for deletion.")
            return False

        url = f"{self.api_url}/files/{file_id}"

        try:
            # Use requests.delete() for DELETE endpoints
            response = requests.delete(url)
            
            # Check for 404 (Not Found) or 500 (Server Error)
            response.raise_for_status()
            
            print(f"✅ File {file_id} deleted successfully.")
            return True

        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to delete file: {e}")
            return False