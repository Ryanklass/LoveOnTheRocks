import os
from dotenv import load_dotenv
from flask import Flask, render_template, redirect, url_for
from openai import OpenAI
import requests
import ffmpeg
from moviepy.editor import *
import random
from textwrap import wrap
from collections import deque
import json
import subprocess
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
import re
import traceback
from datetime import datetime

UPLOAD_TO_YOUTUBE = False

load_dotenv()

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
PEXELS_API_KEY = os.getenv('PEXELS_API_KEY')
UNREAL_SPEECH_API_KEY = os.getenv('UNREAL_SPEECH_API_KEY')

client = OpenAI(api_key=OPENAI_API_KEY)
app = Flask(__name__)
log_messages = []

keywords = [
    'love', 'romance', 'relationships', 'ocean', 'flowers',
    'trees', 'hearts', 'beautiful sky', 'couples',
    'smiling couples', 'cute things', 'affection', 'bonding',
    'commitment', 'marriage', 'soulmates', 'dating',
    'flirting', 'sweetheart', 'together forever', 'true love',
    'wedding', 'couple goals'
]

last_used_music = None

MAX_BANNED_SCRIPTS = 10
banned_scripts = deque(maxlen=MAX_BANNED_SCRIPTS)

BANNED_SCRIPTS_FILE = 'banned_scripts.json'

def save_banned_scripts():
    with open(BANNED_SCRIPTS_FILE, 'w') as f:
        json.dump(list(banned_scripts), f)

def load_banned_scripts():
    global banned_scripts
    if os.path.exists(BANNED_SCRIPTS_FILE):
        with open(BANNED_SCRIPTS_FILE, 'r') as f:
            banned_scripts = deque(json.load(f), maxlen=MAX_BANNED_SCRIPTS)
    else:
        banned_scripts = deque(maxlen=MAX_BANNED_SCRIPTS)

def add_log(message):
    log_messages.append(message)
    print(message)

def generate_script():
    banned_scripts_str = "\n\n".join(banned_scripts) if banned_scripts else "No banned scripts yet."
    prompt = f"""Hi ChatGPT, I want to create a YouTube Shorts channel featuring corny relationship and love quotes/advice. Please provide just one short script, no more than 100 words. Do not ever use emojis or asterisks (*) in your response. EVER!

    Examples format of the scripts (don't actually use these scripts though):
    3 hints he's Crushing on You Hard.
    He remembers the smallest details about you
    He smiles when you walk past him
    He texts you back really fast.
    Another line
    Another line
    (Keep going if needed)
    Love tips
    If they make you laugh even on your worst days, they're a keeper.
    If she picks you up from the airport, she's the one.
    Another line
    Another line
    (Keep going if needed)

    Banned scripts/similiar topics are below. Do not use these exact scripts or very similar topics below:

    {banned_scripts_str}

    VERY IMPORTANT Rules:
    1. I want things like this that are a variety in love/relationship/romance topics. The examples I provided you were just examples. NEVER use the examples as a response/script to me. I want you to create your own. I want you to think of an array of topics that teens would love like gossip, romance, dating, crushes, heartbreak, love at first sight, texting, first dates, last dates, dinner dates, etc. Don't just limit yourself to those topics, use your imagination of what teens talk about and go through. Please also, add in mental health topics as well. 
    2. ALWAYS start the script with a title by itself and nothing else. The title should ALWAYS have a period after it. ALWAYS!
    3. After the title, always put a period.and After the title the text that follows should be on the next line down. And it should follow the examples that I provided above. Which is:
    Title.
    Line
    Line
    Line
    Another line
    Another line
    (Keep going if needed)
    1. The response script should only include the script text with no extra commentary, introductions, or concluding remarks. Only provide the script text. NEVER, EVER include any extra text or commentary. Don't ever stray from this rule ever. You will be banned and punished if you do.
    2. Each point should be on its own line of text.
    3. The scripts should vary in length. Some scripts should be as short as 30 words, while others should be up to 120 words. The length should vary randomly.
    4. For longer scripts, vary the length by sometimes adding more lines and sometimes using longer sentences.
    5. Each script should have a mix of lines, with some being 3 lines, some 4 lines, and some 5 lines. Variation is key.
    6. Ensure that some sentences are longer and more detailed, while others are short and concise.
    7. Sometimes the sentences should be pretty long. Other times sentences should be short. Mix it up. 
    8. The scripts should be a mix of advice, tips, and general information.
    9. There should only ever be one scripts/topic per response. Never more than one.
    10. Do not use any '#' characters in your response.
    11. Do not ever use emojis in your response. EVER!
    12. Keep titles relatively short. And straight to the point. Trendy one liners are best for titles.
    13. VERY IMPORTANT. ALWAYS MAKE SURE THERE IS A PERIOD AFTER THE TITLE AND AFTER EVERY LINE AFTER THAT. NO EXCEPTIONS.I'm sending this script to a text-to-speech api so I need everything formatted correctly.
    14. Make sure the scripts are a 4th grade reading level. VERY IMPORTANT.  
    15. If you have a title that says let's say "The Mystery of Love at First Sight." don't start the first line with the backedn from the title. Meaning, in this case, don't start the first line after the title with "Love at First Sight." always differentiate the title from the first line by having the text be something different and not tailing from the title. 

    Please follow these rules strictly."""

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=200,
        temperature=0.7
    )

    script = response.choices[0].message.content.strip()
    script = script.replace('#', '').replace('*', '')
    
    banned_scripts.append(script)
    save_banned_scripts()
    add_log(f'Generated script: {script}')
    add_log(f'Added to banned scripts list')
    add_log("Full prompt sent to ChatGPT:")
    add_log(prompt)
    add_log("Current banned scripts:")
    add_log(banned_scripts_str)
    
    return script

def fetch_videos():
    selected_keywords = random.sample(keywords, min(len(keywords), 10))
    add_log(f'Selected keywords for search: {selected_keywords}')

    all_videos = []
    for keyword in selected_keywords:
        page = 1
        while len(all_videos) < 100:
            response = requests.get(
                'https://api.pexels.com/videos/search',
                params={
                    'query': keyword,
                    'per_page': 80,
                    'page': page,
                    'orientation': 'portrait',
                    'size': 'medium'
                },
                headers={'Authorization': PEXELS_API_KEY}
            )
            data = response.json()
            if not data['videos']:
                break

            for video in data['videos']:
                suitable_video = next(
                    (
                        file for file in video['video_files']
                        if file['width'] >= 1080 and file['height'] >= 1920
                    ),
                    None
                )
                if suitable_video:
                    video_filename = f"video_{keyword.replace(' ', '_')}_{video['id']}.mp4"
                    all_videos.append({'url': suitable_video['link'], 'filename': video_filename})
            
            page += 1
            if page > data['total_results'] // 80 + 1:
                break

    selected_videos = random.sample(all_videos, min(15, len(all_videos)))
    add_log(f'Videos selected: {selected_videos}')
    return selected_videos

def download_videos(videos):
    for video in videos:
        response = requests.get(video['url'])
        with open(video['filename'], 'wb') as file:
            file.write(response.content)
        add_log(f'Downloaded video: {video["filename"]}')

def resize_video(input_file, output_file, target_width=1080, target_height=1920):
    try:
        probe = ffmpeg.probe(input_file)
        video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
        width = int(video_stream['width'])
        height = int(video_stream['height'])

        input_stream = ffmpeg.input(input_file)
        if width / height > target_width / target_height:
            new_width = int(height * target_width / target_height)
            video = input_stream.filter('crop', new_width, height, (width - new_width) // 2, 0)
        else:
            new_height = int(width * target_height / target_width)
            video = input_stream.filter('crop', width, new_height, 0, (height - new_height) // 2)

        video = video.filter('scale', target_width, target_height)
        output = ffmpeg.output(video, output_file, vcodec='libx264')
        ffmpeg.run(output, overwrite_output=True)
        add_log(f'Resized video: {output_file}')
    except ffmpeg.Error as e:
        add_log(f"Error resizing video: {e.stderr.decode()}")
        raise

def select_random_music():
    global last_used_music
    music_folder = "Music"
    music_files = [f for f in os.listdir(music_folder) if f.endswith('.mp3')]
    if not music_files:
        add_log("No music files found in the Music folder.")
        return None
    
    if len(music_files) == 1:
        selected_music = music_files[0]
    else:
        available_music = [f for f in music_files if f != last_used_music]
        selected_music = random.choice(available_music)
    
    last_used_music = selected_music
    add_log(f"Selected music file: {selected_music}")
    return os.path.join(music_folder, selected_music)

def generate_speech(text, voice_id="Dan", output_file="narration.mp3", speed="0"):
    url = "https://api.v7.unrealspeech.com/speech"
    payload = {
        "Text": text,
        "VoiceId": voice_id,
        "Bitrate": "192k",
        "Speed": speed,
        "Pitch": "1",
        "Codec": "libmp3lame",
        "Temperature": 0.25,
        "TimestampType": "word"
    }
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "Authorization": f"Bearer {UNREAL_SPEECH_API_KEY}"
    }
    
    response = requests.post(url, json=payload, headers=headers)
    
    if response.status_code == 200:
        response_data = response.json()
        add_log(f"API Response: {json.dumps(response_data, indent=2)}")
        
        audio_url = response_data.get('OutputUri')
        timestamps_url = response_data.get('TimestampsUri')
        
        if not audio_url or not timestamps_url:
            add_log("Error: Missing OutputUri or TimestampsUri in the API response")
            return None, None
        
        audio_response = requests.get(audio_url)
        with open(output_file, "wb") as f:
            f.write(audio_response.content)
        
        timestamps_response = requests.get(timestamps_url)
        timestamps = timestamps_response.json()
        
        add_log(f"Speech generated and saved to {output_file}")
        add_log(f"Timestamps retrieved: {json.dumps(timestamps, indent=2)}")
        return output_file, timestamps
    else:
        add_log(f"Error generating speech: {response.status_code}")
        add_log(f"Response content: {response.text}")
        return None, None

def create_final_video(script, videos, text_position='center', text_top_offset=0.4, video_darkness=0.5, fade_out_duration=0, max_font_size=45, music_volume=0.3, min_display_duration=0.5, word_gap=0.1, clip_duration=2, watermark_text="@LoveOnTheRocks3", watermark_font="Roboto-bold.ttf", watermark_position=(320, 1750), watermark_font_size=30, audio_cutoff_time=0.5):
    try:
        lines = script.split('\n')
        content_lines = [line.strip() for line in lines if line.strip()]

        narration_text = " ".join(content_lines)
        narration_file, timestamps = generate_speech(narration_text, speed="0")

        if not narration_file or not timestamps:
            add_log("Failed to generate narration or retrieve timestamps. Aborting video creation.")
            return None, None

        add_log(f"Timestamps received: {json.dumps(timestamps, indent=2)}")

        narration_audio = AudioFileClip(narration_file)
        
        # Cut the narration audio short by audio_cutoff_time seconds
        narration_duration = narration_audio.duration - audio_cutoff_time
        narration_audio = narration_audio.subclip(0, narration_duration)
        
        resized_videos = []
        for video in videos:
            resized_filename = f"resized_{video['filename']}"
            resize_video(video['filename'], resized_filename)
            resized_videos.append(resized_filename)

        video_clips = [VideoFileClip(video) for video in resized_videos]
        video_width, video_height = video_clips[0].w, video_clips[0].h

        font_path = os.path.join(os.getcwd(), 'Roboto-Black.ttf')
        
        def get_font_size(text, max_width, max_size=45, min_size=40):
            for font_size in range(max_size, min_size - 1, -1):
                txt_clip = TextClip(text, fontsize=font_size, font=font_path, color='white')
                if txt_clip.w < max_width:
                    return font_size
            return min_size

        def group_words(words, timestamps, max_chars=20):
            groups = []
            current_group = []
            current_start = None
            current_chars = 0
            
            for i, word in enumerate(words):
                if not current_group:
                    current_start = timestamps[i]['start']
                
                if current_chars + len(word) <= max_chars:
                    current_group.append(word)
                    current_chars += len(word) + 1  # +1 for space
                else:
                    end = timestamps[i-1]['end']
                    groups.append({
                        'text': ' '.join(current_group),
                        'start': current_start,
                        'end': end
                    })
                    current_group = [word]
                    current_chars = len(word)
                    current_start = timestamps[i]['start']
                
                if (i == len(words) - 1 or word.endswith(('.', '!', '?'))):
                    end = timestamps[i]['end']
                    groups.append({
                        'text': ' '.join(current_group),
                        'start': current_start,
                        'end': end
                    })
                    current_group = []
                    current_chars = 0
                    current_start = None
            
            return groups

        words = re.findall(r'\S+|\n', narration_text)
        word_groups = group_words(words, timestamps, max_chars=20)
        
        add_log(f"Total words: {len(words)}")
        add_log(f"Word groups created: {len(word_groups)}")

        text_clips = []
        for i, group in enumerate(word_groups):
            duration = max(group['end'] - group['start'], min_display_duration)
            
            if i < len(word_groups) - 1:
                next_start = word_groups[i+1]['start']
                if group['end'] + word_gap > next_start:
                    duration = next_start - group['start'] - word_gap

            font_size = get_font_size(group['text'], video_width * 0.9, max_font_size, min_size=40)
            
            text_clip = (TextClip(group['text'].upper(), fontsize=font_size, font=font_path, color='white', align='center', stroke_color='black', stroke_width=2)
                         .set_position(('center', 'center'))
                         .set_start(group['start'])
                         .set_duration(duration))
            
            text_clips.append(text_clip)
            add_log(f"Added text clip: '{group['text']}' at time {text_clip.start:.2f} - {text_clip.end:.2f}, font size: {font_size}")

        video_duration = narration_audio.duration + fade_out_duration
        add_log(f"Video duration: {video_duration}")
        
        looped_clips = []
        total_clip_duration = 0
        while total_clip_duration < video_duration:
            for clip in video_clips:
                if total_clip_duration >= video_duration:
                    break
                if clip.duration > clip_duration:
                    looped_clips.append(clip.subclip(0, clip_duration))
                    total_clip_duration += clip_duration
                else:
                    looped_clips.append(clip)
                    total_clip_duration += clip.duration

        combined_clip = concatenate_videoclips(looped_clips)
        combined_clip = combined_clip.set_duration(video_duration)
        darkened_clip = combined_clip.fx(vfx.colorx, video_darkness)
        
        # Create watermark
        watermark_font_path = os.path.join(os.getcwd(), f'{watermark_font}.ttf')
        watermark_clip = (TextClip(watermark_text, fontsize=watermark_font_size, font=watermark_font_path, color='white', align='center', stroke_color='black', stroke_width=1)
                  .set_position(watermark_position)
                  .set_duration(video_duration))

        final_clip = CompositeVideoClip([darkened_clip] + text_clips + [watermark_clip])
        final_clip = final_clip.set_duration(video_duration).fadeout(fade_out_duration)

        add_log(f"Final clip duration: {final_clip.duration}")

        music_file = select_random_music()
        if music_file:
            music_audio = AudioFileClip(music_file)
            if music_audio.duration < video_duration:
                music_audio = music_audio.fx(vfx.loop, duration=video_duration)
            else:
                music_audio = music_audio.subclip(0, video_duration)
            music_audio = music_audio.volumex(music_volume)

            combined_audio = CompositeAudioClip([narration_audio, music_audio])
            final_clip = final_clip.set_audio(combined_audio)
        else:
            final_clip = final_clip.set_audio(narration_audio)

        # Create a "Videos" folder if it doesn't exist
        videos_folder = os.path.join(os.getcwd(), "Videos")
        if not os.path.exists(videos_folder):
            os.makedirs(videos_folder)

        # Generate a unique filename using timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        final_output = os.path.join(videos_folder, f'final_output_{timestamp}.mp4')
        
        final_clip.write_videofile(final_output, temp_audiofile="temp-audio.m4a", remove_temp=True, codec="libx264", audio_codec="aac")

        add_log(f'Final video created with narration and background music: {final_output}')

        # Clean up temporary files
        for video in resized_videos:
            if os.path.exists(video):
                os.remove(video)
                add_log(f'Removed resized file: {video}')

        if os.path.exists(narration_file):
            os.remove(narration_file)
            add_log(f'Removed narration file: {narration_file}')

        return final_output, content_lines[0]  # Return the first line as the title
    except Exception as e:
        add_log(f"Error in create_final_video: {str(e)}")
        add_log(f"Error traceback: {traceback.format_exc()}")
        return None, None

def cleanup():
    for filename in os.listdir('.'):
        if filename.startswith('video_') and filename.endswith('.mp4'):
            os.remove(filename)
            add_log(f'Removed temporary file: {filename}')
    
    # Remove any temporary files in the Videos folder
    videos_folder = os.path.join(os.getcwd(), "Videos")
    if os.path.exists(videos_folder):
        for filename in os.listdir(videos_folder):
            if filename.startswith('temp_') and filename.endswith('.mp4'):
                os.remove(os.path.join(videos_folder, filename))
                add_log(f'Removed temporary file from Videos folder: {filename}')

def get_authenticated_service():
    SCOPES = ['https://www.googleapis.com/auth/youtube.upload']
    flow = InstalledAppFlow.from_client_secrets_file('client_secret.json', SCOPES)
    credentials = flow.run_local_server(port=8080)  # Use port 8080 for OAuth
    return build('youtube', 'v3', credentials=credentials)

def upload_video(youtube, file, title, description):
    body = {
        'snippet': {
            'title': title,
            'description': description,
            'tags': ['love', 'relationships', 'advice'],
            'categoryId': '22'  # People & Blogs category
        },
        'status': {
            'privacyStatus': 'private'  # or 'public' or 'unlisted'
        }
    }

    media = MediaFileUpload(file, resumable=True)

    try:
        insert_request = youtube.videos().insert(
            part=','.join(body.keys()),
            body=body,
            media_body=media
        )
        response = insert_request.execute()
        add_log(f"Video uploaded successfully. Video ID: {response['id']}")
        return response['id']
    except Exception as e:
        add_log(f"An error occurred while uploading the video: {str(e)}")
        return None

@app.route('/')
def home():
    return render_template('index.html', log_messages=log_messages)

@app.route('/generate_videos/<int:count>')
def generate_videos_route(count):
    print(f"Entering generate_videos_route to create {count} videos")
    try:
        for i in range(count):
            print(f"Generating video {i+1} of {count}")
            script = generate_script()
            print(f"Script generated: {script}")
            videos = fetch_videos()
            print(f"Videos fetched: {videos}")
            download_videos(videos)
            final_video, video_title = create_final_video(
                script, videos, 
                text_position='center', 
                text_top_offset=0.5, 
                video_darkness=0.7, 
                fade_out_duration=0, 
                max_font_size=80, 
                music_volume=0.25, 
                min_display_duration=0.7, 
                word_gap=0.1,
                clip_duration=2.5,
                watermark_text="@LoveOnTheRocks3",
                watermark_font="Roboto-bold.ttf",
                watermark_position=(320, 1750),
                watermark_font_size=45,
                audio_cutoff_time=0.5  # Add this new parameter
            )
            
            if UPLOAD_TO_YOUTUBE:
                print("Uploading video to YouTube")
                youtube = get_authenticated_service()
                video_id = upload_video(youtube, final_video, video_title, script)
                if video_id:
                    add_log(f"Video uploaded successfully. Video ID: {video_id}")
                else:
                    add_log("Failed to upload video to YouTube.")
            else:
                print("YouTube upload is disabled. Video not uploaded.")
                add_log("YouTube upload is disabled. Video not uploaded.")
            
            print("Cleaning up")
            cleanup()
            
        add_log(f"Successfully generated {count} videos")
    except Exception as e:
        print(f"Error occurred: {str(e)}")
        add_log(f'Error: {str(e)}')
    print("Redirecting to home")
    return redirect(url_for('home'))

if __name__ == '__main__':
    load_banned_scripts()
    app.run(debug=True, use_reloader=False, port=5001)
       
        

