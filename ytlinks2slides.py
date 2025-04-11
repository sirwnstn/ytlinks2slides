#!/usr/bin/env python3

import os
import re
import argparse
from urllib.parse import urlparse, parse_qs
import google.auth
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import requests
from bs4 import BeautifulSoup

# If modifying these scopes, delete the token.json file
SCOPES = ['https://www.googleapis.com/auth/presentations', 'https://www.googleapis.com/auth/youtube.readonly']

def get_credentials():
    """Gets valid user credentials from storage.
    
    If nothing has been stored, or if the stored credentials are invalid,
    the OAuth 2.0 flow is completed to obtain the new credentials.
    
    Returns:
        Credentials, the obtained credential.
    """
    creds = None
    # The file token.json stores the user's access and refresh tokens
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_info(json.loads(open('token.json').read()))
    
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    
    return creds

def extract_video_id(youtube_url):
    """Extract the video ID from a YouTube URL."""
    # Parse the URL
    parsed_url = urlparse(youtube_url)
    
    # Get video ID from URL query parameters (e.g., youtube.com/watch?v=VIDEO_ID)
    if parsed_url.hostname in ('www.youtube.com', 'youtube.com'):
        if parsed_url.path == '/watch':
            return parse_qs(parsed_url.query)['v'][0]
    
    # Get video ID from youtu.be URLs (e.g., youtu.be/VIDEO_ID)
    elif parsed_url.hostname == 'youtu.be':
        return parsed_url.path[1:]
    
    # Get video ID from embedded URLs (e.g., youtube.com/embed/VIDEO_ID)
    elif parsed_url.path.startswith('/embed/'):
        return parsed_url.path.split('/')[2]
    
    # If we get here, we couldn't extract the video ID
    raise ValueError(f"Could not extract video ID from URL: {youtube_url}")

def get_video_title(video_id, youtube_service=None):
    """Get the title of a YouTube video."""
    if youtube_service:
        # Use YouTube API if service is provided
        response = youtube_service.videos().list(
            part="snippet",
            id=video_id
        ).execute()
        
        if response['items']:
            return response['items'][0]['snippet']['title']
        else:
            return f"Video {video_id}"
    else:
        # Fallback: scrape the title from the webpage
        try:
            url = f"https://www.youtube.com/watch?v={video_id}"
            response = requests.get(url)
            soup = BeautifulSoup(response.text, 'html.parser')
            return soup.find('title').text.replace(' - YouTube', '')
        except Exception as e:
            print(f"Error getting title for video {video_id}: {e}")
            return f"Video {video_id}"

def create_slides_presentation(title):
    """Create a new Google Slides presentation."""
    creds = get_credentials()
    slides_service = build('slides', 'v1', credentials=creds)
    
    presentation = {
        'title': title
    }
    
    presentation = slides_service.presentations().create(body=presentation).execute()
    print(f"Created presentation with ID: {presentation['presentationId']}")
    
    # Delete the default slide
    slides_service.presentations().batchUpdate(
        presentationId=presentation['presentationId'],
        body={
            'requests': [
                {
                    'deleteObject': {
                        'objectId': 'p'
                    }
                }
            ]
        }
    ).execute()
    
    return presentation['presentationId'], slides_service

def add_video_slide(presentation_id, slides_service, video_id, video_title):
    """Add a slide with an embedded YouTube video."""
    # Create a new slide
    slide_id = f"slide_{video_id}"
    title_id = f"title_{video_id}"
    video_box_id = f"video_{video_id}"
    
    # Add a new slide with layout for title and video
    slides_service.presentations().batchUpdate(
        presentationId=presentation_id,
        body={
            'requests': [
                {
                    'createSlide': {
                        'objectId': slide_id,
                        'insertionIndex': '0',
                        'slideLayoutReference': {
                            'predefinedLayout': 'TITLE_ONLY'
                        },
                        "placeholderIdMappings": [
                            {
                                "layoutPlaceholder": {
                                "type": "TITLE",
                                "index": 0
                                },
                                "objectId": title_id,
                            }
                        ]
                    }
                },
                {
                    "insertText": {
                        "objectId": title_id,
                        "text": video_title
                    }
                }
            ]
        }
    ).execute()
    
    # Add title to the slide
    # slides_service.presentations().batchUpdate(
    #     presentationId=presentation_id,
    #     body={
    #         'requests': [
    #             {
    #                 'createShape': {
    #                     'objectId': title_id,
    #                     'shapeType': 'TEXT_BOX',
    #                     'elementProperties': {
    #                         'pageObjectId': slide_id,
    #                         'size': {
    #                             'width': {'magnitude': 720, 'unit': 'PT'},
    #                             'height': {'magnitude': 50, 'unit': 'PT'}
    #                         },
    #                         'transform': {
    #                             'scaleX': 1,
    #                             'scaleY': 1,
    #                             'translateX': 40,
    #                             'translateY': 20,
    #                             'unit': 'PT'
    #                         }
    #                     }
    #                 }
    #             },
    #             {
    #                 'insertText': {
    #                     'objectId': title_id,
    #                     'text': video_title
    #                 }
    #             }
    #             # ,
    #             # {
    #             #     'updateTextStyle': {
    #             #         'objectId': title_id,
    #             #         'textRange': {
    #             #             'type': 'ALL'
    #             #         },
    #             #         'style': {
    #             #             'fontSize': {
    #             #                 'magnitude': 24,
    #             #                 'unit': 'PT'
    #             #             },
    #             #             'fontWeight': 'BOLD'
    #             #         },
    #             #         'fields': 'fontSize,fontWeight'
    #             #     }
    #             # }
    #         ]
    #     }
    # ).execute()

    # Calculate dimensions for 16:9 video that maximizes the slide area
    # Standard slide size is 720x405 PT (10x7.5 inches at 72 DPI)
    # Let's position the video to take most of the slide while keeping margins
    video_width = 720  # PT
    video_height = 405  # PT (16:9 ratio)
    
    # Add video to the slide with autoplay parameter
    slides_service.presentations().batchUpdate(
        presentationId=presentation_id,
        body={
            'requests': [
                {
                    'createVideo': {
                        'objectId': video_box_id,
                        'id': video_id,
                        'source': 'YOUTUBE',
                        'elementProperties': {
                            'pageObjectId': slide_id,
                            'size': {
                                'width': {'magnitude': video_width, 'unit': 'PT'},
                                'height': {'magnitude': video_height, 'unit': 'PT'}
                            }
                            # ,
                            # 'transform': {
                            #     'scaleX': 1,
                            #     'scaleY': 1,
                            #     'translateX': (720 - video_width) / 2,  # Center horizontally
                            #     'translateY': 80,  # Position below title
                            #     'unit': 'PT'
                            # }
                        }
                        # ,
                        # "videoProperties": {
                        #     "autoPlay": True
                        # }
                    }
                },
                {
                    'updateVideoProperties': {
                        'objectId': video_box_id,
                        "videoProperties": {
                                "autoPlay": True
                            },
                        "fields": "autoPlay"
                    }
                }
            ]
        }
    ).execute()
    
    print(f"Added slide for video: {video_title}")

def main():
    """Create a Google Slides presentation from YouTube links."""
    import json
    
    parser = argparse.ArgumentParser(description='Create Google Slides from YouTube videos')
    parser.add_argument('--input', '-i', type=str, required=True, 
                        help='File containing YouTube URLs (one per line)')
    parser.add_argument('--title', '-t', type=str, default='YouTube Videos Presentation',
                        help='Title for the presentation')
    args = parser.parse_args()
    
    # Authenticate and build services
    creds = get_credentials()
    youtube_service = build('youtube', 'v3', credentials=creds)
    
    # Create a new presentation
    presentation_id, slides_service = create_slides_presentation(args.title)
    
    # Read YouTube URLs from file
    with open(args.input, 'r') as f:
        youtube_urls = [line.strip() for line in f if line.strip()]
    
    # Process each YouTube URL
    for url in youtube_urls:
        try:
            video_id = extract_video_id(url)
            video_title = get_video_title(video_id, youtube_service)
            add_video_slide(presentation_id, slides_service, video_id, video_title)
        except Exception as e:
            print(f"Error processing URL {url}: {e}")
    
    print(f"Presentation created successfully: https://docs.google.com/presentation/d/{presentation_id}/edit")

if __name__ == "__main__":
    import json  # For handling token.json
    main()