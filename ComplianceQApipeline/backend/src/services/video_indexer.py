'''
Connector : Python and Azure video indexer
'''
import os
import time
import logging
import requests
import yt_dlp
from azure.identity import DefaultAzureCredential

logger = logging.getLogger("video-indexer")

class VideoIndexerService:
    def __init__(self):
            self.account_id = os.getenv("AZURE_VI_ACCOUNT_ID")
            self.location = os.getenv("AZURE_VI_LOCATION")
            self.subscription_id = os.getenv("AZURE_SUBSCRIPTION_ID")
            self.resource_group = os.getenv("AZURE_RESOURCE_GROUP")
            self.vi_name = os.getenv("AZURE_VI_NAME", "Vindexer-ad-gaurd-8187")
            self.credential = DefaultAzureCredential()

    def get_access_token(self):
        """
        Get the access token for Azure Video Indexer API
        """
        try:
            token_object = self.credential.get_token("https://management.azure.com/.default")
            return token_object.token
        except Exception as e:
            logger.error(f"Failed to get Azure token: {e}")
            raise
    
    def get_account_token(self, arm_access_token):
        '''
        Exchanges the ARM token for Video indexer account team
        '''
        url = (
            f"https://management.azure.com/subscriptions/{self.subscription_id}"
            f"/resourceGroups/{self.resource_group}"
            f"/providers/Microsoft.VideoIndexer/accounts/{self.vi_name}"
            f"/generateAccessToken?api-version=2024-01-01"
        )
        headers = {"Authorization": f"Bearer {arm_access_token}"}
        payload = {"permissionType": "Contributor", "scope": "Account"}
        response = requests.post(url, headers=headers, json=payload)

        if response.status_code != 200:
            raise Exception(f"Failed to ge VI Account token : {response.text}")

        return response.json().get("accessToken")
    

    #function to download the youtube URL
    def download_youtube_video(self, url, output_path="temp_video.mp4"):
        """
        Download the youtube video using yt-dlp to a local file
        """
        logger.info(f"Downloading video from URL: {url}")
        ydl_opts = {
            'format': 'best',
            'outtmpl': output_path,
            'quiet': True,
            'overwrites': True,
            'no_warnings': True,
            'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
            'http_headers': {
                 'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            logger.info("Video downloaded successfully.")
            return output_path
        except Exception as e:
            raise Exception(f"Failed to download video: {str(e)}")

    #Upload video to Azure video indexer
    def upload_video(self,video_path, video_name):
        arm_token = self.get_access_token()
        vi_token = self.get_account_token(arm_token)

        api_url = f"https://api.videoindexer.ai/{self.location}/Accounts/{self.account_id}/Videos"

        parms = {
            "accessToken": vi_token,
            "name": video_name,
            "privacy": "Private",
            "indexingPreset": "Default"
        }

        logger.info(f"Uploading video to Azure Video Indexer: {video_path}")

        #open the file in binary mode and stream it on Azure
        with open(video_path, "rb") as video_file:
            files = {"file":  video_file}
            response = requests.post(api_url, params=parms, files=files)

        if response.status_code != 200:
            raise Exception(f"Failed to upload video: {response.text}")
        
        return response.json().get("id")
        
    def wait_for_processing(self, video_id):
        '''
        Wait for the video to be processed and indexed by Azure Video Indexer
        '''
        logger.info(f"Waiting for video processing to complete for video ID: {video_id}")
        while True:
            arm_token = self.get_access_token()
            vi_token = self.get_account_token(arm_token)

            url = f"https://api.videoindexer.ai/{self.location}/Accounts/{self.account_id}/Videos/{video_id}/Index"
            params = {"accessToken": vi_token}
            response = requests.get(url, params=params)
            data = response.json()

            state = data.get("state")
            if state == "Processed":
                return data
            elif state == "Failed":
                raise Exception("Video Indexing failed in Azure.")
            elif state == "Quarantined":
                raise Exception("Video is quarantined in Azure Video Indexer due to copyright issues.")
            logger.info(f"Status{state}..... waiting for 30 seconds before checking again.")
            time.sleep(30)


    def extract_data(self, vi_json):
        """
        Extract relevant data from the Azure Video Indexer JSON response.
        """
        transcript_lines = []
        for v in vi_json.get("videos", []):
            for insight in v.get("insights", {}).get("transcript", []):
                transcript_lines.append(insight.get("text"))

        ocr_lines = []
        for v in vi_json.get("videos", []):
            for insight in v.get("insights", {}).get("ocr", []):
                ocr_lines.append(insight.get("text"))
        return {
            "transcript": " ".join(transcript_lines),
            "ocr": ocr_lines,
            "video_metadata": {
                "duration": vi_json.get("summarizedInsights", {}).get("duration"),
                "platform": "Youtube"
            }
        }