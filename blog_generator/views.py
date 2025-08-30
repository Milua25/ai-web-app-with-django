import os.path
import random
from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import login, logout,authenticate
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.http import JsonResponse
import json
from pytubefix import YouTube
from pytubefix.cli import on_progress
import assemblyai as aai
import asyncio
from openai import AsyncOpenAI, OpenAIError
from .models import BlogPost
import httpx

# Create your views here.
@login_required
def index(request):
    return render(request, 'index.html')

# Create login views here.
def user_login(request):
    if request.method == "POST":
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('index')
        else:
            error_message = "Invalid Username or Password"
            return render(request, 'login.html', error_message)
    else:
        return render(request, 'login.html')

# Create logout views here.
def user_logout(request):
    logout(request)
    print("User logged out!!")
    return redirect('index')

# Create signup views here.
def user_signup(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        repeat_password = request.POST.get('repeatPassword')
        if password == repeat_password:
            try:
                print("Creating new user")
                user = User.objects.create_user(username, email, password)
                user.save()
                print('user saved successfully in!!')
                login(request, user)
                return redirect('index')
            except Exception as e:
                print(f"ERROR: {e}")
                error_message = "Error creating account"
                return render(request, 'signup.html', {'error_message': error_message})
        else:
            error_message = "Passwords don't match"
            return render(request, 'signup.html', {'error_message': error_message})
    else:
        return render(request, 'signup.html')

@csrf_exempt
def generate_blog(request):
    if request.method == "POST":
        try:
            print("Creating new blog")
            data = json.loads(request.body)
            yt_link = data['link']

        except(KeyError, json.decoder.JSONDecodeError):
            error_message = "Invalid data sent"
            return JsonResponse({'error': error_message}, status=400)

        # Get Title of the video
        title = yt_title(yt_link)
        print("Youtube Title: {}".format(title))

        # Get Transcript
        transcription = get_transcript(yt_link)
        if not transcription:
            return JsonResponse({'error': 'No transcription found'}, status=500)

        # Use OpenAI to generate the blog
        blog_content = asyncio.run(generate_blog_from_transcription(transcription))
        if not blog_content:
            return JsonResponse({'error': 'Failed to generate blog content'}, status=500)

        # Save blog Article to database
        new_blog_article = BlogPost(
            user=request.user,
            youtube_title=title,
            youtube_link=yt_link,
            generated_content=blog_content,
        )

        new_blog_article.save()
        print("Blog post saved")

        # Return blog article as response
        return JsonResponse({'content': blog_content})

    else:
        return JsonResponse({
         'error':  "Invalid Request Method"
        }, status=405)

# Get YouTube title
def yt_title(link):
    yt = YouTube(link, on_progress_callback=on_progress)
    title = yt.title
    return title

def get_transcript(link):
    audio_file = download_audio(link)
    aai.settings.api_key = os.getenv("TRANSCRIBER_API_KEY")
    transcriber = aai.Transcriber()
    try:
        transcript = transcriber.transcribe(audio_file)
    except Exception as e:
        print("ERROR: {}".format(e))
        return JsonResponse({
         'error':  "Unable to transcribe audio file"
        }, status=500)

    print("Transcript: {}".format(transcript))
    return transcript.text

async def generate_blog_from_transcription(transcription):
        prompt = f"Based on the following transcript from a YouTube video, write a comprehensive blog article, write it based on the transcript, but dont make it look like a youtube video, make it look like a proper blog article:\n\n{transcription}\n\nArticle:"
        client = AsyncOpenAI(
            api_key= os.getenv("OPENAI_API_KEY")
        )
        for attempt in range(10):
            try:
                response = await client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "You are a helpful writing assistant."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=1000
                )
                print(response)
                generated_content = response.choices[0].message.content.strip()
                return generated_content
            except (httpx.RequestError, OpenAIError) as e:
                wait_time = 2 ** attempt + random.random()
                print(f"Error: {e}. Retrying in {wait_time:.2f}s...")
                await asyncio.sleep(wait_time)
        return "Failed to generate blog article after multiple attempts."

def download_audio(link):
    yt = YouTube(link)
    audio = yt.streams.filter(only_audio=True).first()
    out_file = audio.download(output_path=settings.MEDIA_ROOT)
    base, ext = os.path.splitext(out_file)
    new_file = base + ".mp3"
    os.rename(out_file, new_file)
    return new_file

def blog_posts(request):
    blog_articles = BlogPost.objects.filter(user=request.user)
    return render(request, 'all-blogs.html', {'blog_articles': blog_articles})

def blog_posts_id(request,post_id):
    blog_article = BlogPost.objects.get(id=post_id)
    if request.user == blog_article.user:
        return render(request, 'blog-details.html', {'blog_article_detail': blog_article})
    else:
        return redirect('index')
