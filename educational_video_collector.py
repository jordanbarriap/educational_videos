# Sample Python code for user authorization
from __future__ import unicode_literals

import sys

sys.path.insert(1, '/Library/Python/2.7/site-packages')

import os
import youtube_dl

import google.oauth2.credentials

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google_auth_oauthlib.flow import InstalledAppFlow
# from oauth2client.tools import argparser
import argparse
import time

import re
from bs4 import BeautifulSoup
import lxml

import json

from datetime import timedelta
from datetime import datetime

import unicodedata

from gensim.models import KeyedVectors
from gensim.test.utils import datapath
from gensim.models import Word2Vec

# The CLIENT_SECRETS_FILE variable specifies the name of a file that contains
# the OAuth 2.0 information for this application, including its client_id and
# client_secret.
CLIENT_SECRETS_FILE = "client_secret.json"

# This OAuth 2.0 access scope allows for full read/write access to the
# authenticated user's account and requires requests to use an SSL connection.
SCOPES = ['https://www.googleapis.com/auth/youtube.force-ssl']
API_SERVICE_NAME = 'youtube'
API_VERSION = 'v3'
#DEVELOPER_KEY = 'AIzaSyBlp0ZxBFcPycThdmM21gkGCvOw8WrSL_A'
DEVELOPER_KEY = 'AIzaSyAREfiLO-6llzgoZLasXXKujmsWXqukHRs'

PATH_FOLDER_CONCEPTS = "./sections_to_analyze/"
MAX_RESULTS = 10

# Threshold to identify if the collected video is relevant or not for the current section (.05 means that the video should contain at least a 5% of the concepts associated to the specific section)
THRESHOLD_CONCEPTS_PROPORTION = .05
GENERAL_TOPIC = "information retrieval"

# Prepare a summary about the automatic video collection
summary_video_collection = {}

# List to store prerequisite and outcome relationships between concepts
prerequisite_concepts = []
outcome_concepts = []


def get_authenticated_service():
    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
    credentials = flow.run_console()
    return build(API_SERVICE_NAME, API_VERSION, credentials=credentials)


def channels_list_by_username(service, **kwargs):
    results = service.channels().list(
        **kwargs
    ).execute()

    print('This channel\'s ID is %s. Its title is %s, and it has %s views.' %
          (results['items'][0]['id'],
           results['items'][0]['snippet']['title'],
           results['items'][0]['statistics']['viewCount']))


# Main youtube search function
def youtube_search(options, results_folder):
    youtube = build(API_SERVICE_NAME, API_VERSION,
                    developerKey=DEVELOPER_KEY)

    # Call the search.list method to retrieve results matching the specified
    # query term.
    search_response = youtube.search().list(
        q=options.q,
        part="id,snippet",
        maxResults=options.max_results
    ).execute()

    videos = []
    channels = []
    playlists = []

    # Add each result to the appropriate list, and then display the lists of
    # matching videos, channels, and playlists.
    for search_result in search_response.get("items", []):
        if search_result["id"]["kind"] == "youtube#video":
            videos.append("%s (%s)" % (search_result["snippet"]["title"],
                                       search_result["id"]["videoId"]))
            video_url = "https://www.youtube.com/watch?v=" + search_result["id"]["videoId"]

            video_title = search_result["snippet"]["title"]

            cleaned_video_title = clean_video_title(video_title)

            # Download video subtitles
            result = download_subtitles(video_url, results_folder)

            if video_title in summary_video_collection.keys():
                summary_video_collection[video_title]["query"].append(options.q)
                summary_video_collection[video_title]["num_matches"] = summary_video_collection[video_title]["num_matches"] + 1
            else:
                summary_video_collection[video_title] = {"query": [options.q], "num_matches": 1}

            with open("./" + results_folder + "/summary_video_collection_"+results_folder+".json", "w") as json_file:
                     json.dump(summary_video_collection, json_file)

            # process_subtitles(results_folder, cleaned_video_title)

        elif search_result["id"]["kind"] == "youtube#channel":
            channels.append("%s (%s)" % (search_result["snippet"]["title"],
                                         search_result["id"]["channelId"]))
        elif search_result["id"]["kind"] == "youtube#playlist":
            playlists.append("%s (%s)" % (search_result["snippet"]["title"],
                                          search_result["id"]["playlistId"]))

    print "Videos:\n", "\n".join(videos), "\n"
    print "Channels:\n", "\n".join(channels), "\n"
    print "Playlists:\n", "\n".join(playlists), "\n"


def download_subtitles(video_url, results_folder, lang="en"):
    # cmd = [
    #     "youtube-dl",
    #     "--skip-download",
    #     "--write-sub",
    #     "--sub-lang",
    #     lang,
    #     video_url
    # ]
    #
    # os.system(" ".join(cmd))
    ydl = youtube_dl.YoutubeDL(
        # parameters for setting the youtube-dl
        params={'outtmpl': './' + results_folder + '/%(title)s/%(title)s.%(ext)s',  # format
                'writeautomaticsub': True,  # Get automatic subtitle if exist
                'writesubtitles': True,  # Get manual subtitle if exist
                'skip_download': True,  # Do not download the video
                'writeinfojson': True,  # Get meta info
                'forcefilename': True,
                'restrictfilenames': True
                })
    result = ""
    try:
        with ydl:
            result = ydl.extract_info(
                # Get 5 results from ytsearch, with topic + keyword as query
                url=video_url,
                # Download the content
                download=True
            )
    except youtube_dl.utils.DownloadError as youtube_dl_e:
        print youtube_dl_e

    return result


def prepare_search_args(query, max_results):
    argparser = argparse.ArgumentParser(conflict_handler='resolve')
    argparser.add_argument("--q", help="Search term", default=query)
    argparser.add_argument("--max-results", help="Max results", default=max_results)
    args = argparser.parse_args()
    return args


def video_relevant_for_section(folder_name, video_name):
    relevant = False
    try:
        json_video = open("./" + folder_name + "/" + video_name + "/" + video_name + ".info.json")
        data_video = json.load(json_video)
        if "relevant_to_section" in data_video.keys():
            relevant_string = data_video["relevant_to_section"]
            if relevant_string:
                relevant = True
    except IOError as e:
        print "No json video data found!"
        print e
    return relevant


def fix_video_transcripts_from_timestamped_subtitles(folder_name, video_name):
    transcript = ""
    try:
        json_video = open("./" + folder_name + "/" + video_name + "/" + video_name + ".info.json")
        data_video = json.load(json_video)
        if "timestamped_transcript" in data_video.keys() and len(data_video["timestamped_transcript"]) > 0:
            timestamped_transcript_list = data_video["timestamped_transcript"]
            print data_video["fulltitle"]
            for subtitle in timestamped_transcript_list:
                if "text" in subtitle.keys():
                    transcript = transcript + " " + subtitle["text"]
            data_video["transcript"] = transcript
            with open("./" + folder_name + "/" + video_name + "/" + video_name + ".info.json", "w") as json_file:
                json.dump(data_video, json_file)
    except IOError as e:
        print "No json video data found!"
        print e


def process_subtitles(folder_name, video_name):
    json_path = "./" + folder_name + "/" + video_name + "/" + video_name + ".info.json"
    json_exists = os.path.isfile(json_path)
    while not json_exists:
        print "Json " + json_path + " not ready yet!"
        json_path = json_path.replace('_amp_', '_')
        time.sleep(1)
        json_exists = os.path.isfile(json_path)
    try:
        json_video = open("./" + folder_name + "/" + video_name + "/" + video_name + ".info.json")
        data_video = json.load(json_video)
        transcript = ""
        description = data_video["description"]
        tags = " ".join(data_video["tags"])
        full_title = data_video["fulltitle"]
        try:
            with open("./" + folder_name + "/" + video_name + "/" + video_name + ".en.vtt") as subtitles_lines:
                data_video["timestamped_transcript"] = []
                line_counter = 1
                start_line = False
                autogenerated_subtitles = False
                time_line = False
                current_line = ""
                new_subtitle = {}
                for line in subtitles_lines:
                    line = line.decode('utf8')
                    line = line.strip()
                    if line[:3] == "00:":
                        start_line = True
                    elif line[:3] == "##":
                        autogenerated_subtitles = True
                        print "Autogenerated subtitles!"
                    if line != "" and start_line:
                        time_regexp = re.compile(r'\d\d:\d\d:\d\d.\d\d\d --> \d\d:\d\d:\d\d.\d\d\d')
                        is_time = time_regexp.search(line)
                        if is_time:
                            time_line = True
                            line = is_time.group(0)
                            time_info = line.split("-->")
                            start_time = time_info[0].strip()
                            end_time = time_info[1].strip()

                            start_time_formatted = datetime.strptime(start_time, '%H:%M:%S.%f')
                            end_time_formatted = datetime.strptime(end_time, '%H:%M:%S.%f')
                            time_duration_subtitle = end_time_formatted - start_time_formatted
                            time_duration_subtitle_seconds = time_duration_subtitle.seconds
                            time_duration_subtitle_microseconds = time_duration_subtitle.microseconds

                            # if current_line != "":
                            #     new_subtitle["text"] = current_line
                            #     transcript = transcript + current_line
                            #     current_line = ""

                            # If the subtitle duration is too short (specifically 10000 microseconds after manual
                            # inspection of the data source, we should not take into account the content of the subtitle
                            if time_duration_subtitle_seconds > 0 or time_duration_subtitle_microseconds > 50000:

                                # print new_subtitle
                                new_subtitle["text"] = current_line
                                transcript = transcript + " " + current_line

                                if new_subtitle:
                                    data_video["timestamped_transcript"].append(new_subtitle)
                                # print "Start time: " + start_time + " - End time: " + end_time
                                new_subtitle = {"stime": start_time, "etime": end_time}
                            current_line = ""
                        else:
                            line = re.sub('<[^<]+?>', '', line)
                            if not time_line:
                                current_line = current_line + " " + line
                            else:
                                current_line = line
                                time_line = False
                        line_counter = line_counter + 1

                if current_line != "":
                    new_subtitle["text"] = current_line
                    transcript = transcript + current_line
                # print new_subtitle
                if new_subtitle:
                    data_video["timestamped_transcript"].append(new_subtitle)
                # Add full text of the transcript
                data_video["transcript"] = transcript
                # Counting how many of the prerequisite concepts appear in the video transcripts
                num_concepts = 0
                concepts_list = []
                total_prereq_concepts = len(prerequisite_concepts)
                total_outcome_concepts = len(outcome_concepts)
                expanded_transcript = full_title + " " + description + " " + tags + " " + transcript
                for prerequisite_concept in prerequisite_concepts:
                    if prerequisite_concept in expanded_transcript and prerequisite_concept != "ir":
                        concepts_list.append(prerequisite_concept)
                        num_concepts = num_concepts + 1
                for outcome_concept in outcome_concepts:
                    if outcome_concept in expanded_transcript and outcome_concept != "ir":
                        concepts_list.append(outcome_concept)
                        num_concepts = num_concepts + 1

                proportion_concepts_appearing = float(
                    num_concepts / float(total_prereq_concepts + total_outcome_concepts))

                data_video["concepts_matched"] = concepts_list
                data_video["proportion_concepts_matched"] = proportion_concepts_appearing

                print "Concepts appearing: " + str(num_concepts)
                print concepts_list

                print "Percentage of concepts appearing: " + str(proportion_concepts_appearing)

                # Uses a threshold for matching concepts for defining a video as relevant or not for a specific section
                if num_concepts > 0 and proportion_concepts_appearing >= THRESHOLD_CONCEPTS_PROPORTION:
                    data_video["relevant_to_section"] = True
                else:
                    data_video["relevant_to_section"] = False

                # Overwrite info json that did not include transcripts
                json_video.close()
                with open("./" + folder_name + "/" + video_name + "/" + video_name + ".info.json", "w") as json_file:
                    json.dump(data_video, json_file)


        except IOError as e:
            print "No subtitles file found!"
            print e

            # Counting how many of the prerequisite concepts appear in the video transcripts
            num_concepts = 0
            concepts_list = []
            total_prereq_concepts = len(prerequisite_concepts)
            total_outcome_concepts = len(outcome_concepts)
            alt_transcript = full_title + " " + description + " " + tags
            for prerequisite_concept in prerequisite_concepts:
                if prerequisite_concept in alt_transcript and prerequisite_concept != "ir":
                    concepts_list.append(prerequisite_concept)
                    num_concepts = num_concepts + 1
            for outcome_concept in outcome_concepts:
                if outcome_concept in alt_transcript and outcome_concept != "ir":
                    concepts_list.append(outcome_concept)
                    num_concepts = num_concepts + 1

            proportion_concepts_appearing = float(
                num_concepts / float(total_prereq_concepts + total_outcome_concepts))

            data_video["alternative_transcript"] = alt_transcript
            data_video["concepts_matched"] = concepts_list
            data_video["proportion_concepts_matched"] = proportion_concepts_appearing

            print "Concepts appearing: " + str(num_concepts)
            print concepts_list

            print "Percentage of concepts appearing: " + str(proportion_concepts_appearing)

            # Uses a threshold for matching concepts for defining a video as relevant or not for a specific section
            if num_concepts > 0 and proportion_concepts_appearing >= THRESHOLD_CONCEPTS_PROPORTION:
                data_video["relevant_to_section"] = True
            else:
                data_video["relevant_to_section"] = False

            # Overwrite info json that did not include transcripts
            json_video.close()
            with open("./" + folder_name + "/" + video_name + "/" + video_name + ".info.json", "w") as json_file:
                json.dump(data_video, json_file)
    except IOError as e:
        print "No json video data found!"
        print e


def remove_accents(input_str):
    nfkd_form = unicodedata.normalize('NFKD', input_str)
    only_ascii = nfkd_form.encode('ASCII', 'ignore')
    return only_ascii


def clean_video_title(video_title):
    cleaned_video_title = video_title.replace(': ', ' - ')

    cleaned_video_title = remove_accents(cleaned_video_title)

    # Remove specific character that was given problems in iir.2.4 u\0097
    cleaned_video_title = re.sub(r'[^\x00-\x7f]', r' ', cleaned_video_title)

    # cleaned_video_title = cleaned_video_title.encode('ascii', errors='ignore')

    cleaned_video_title = re.sub('[<>"|?!*{}[\]#]', '', cleaned_video_title)  # () was previously here
    cleaned_video_title = re.sub('[&]', 'amp', cleaned_video_title)

    cleaned_video_title = re.sub('[/\',()]', ' ', cleaned_video_title)
    time_regexp = re.compile(r'\d:\d')
    has_time_exp = time_regexp.search(cleaned_video_title)
    if has_time_exp:
        print "It has d:d format inside"
        cleaned_video_title = re.sub('[:]', ' ', cleaned_video_title)
    else:
        cleaned_video_title = re.sub('[:]', ' -', cleaned_video_title)
    cleaned_video_title = cleaned_video_title.strip()
    cleaned_video_title = re.sub(' +', ' ', cleaned_video_title)
    cleaned_video_title = re.sub('[ ]', '_', cleaned_video_title)

    return cleaned_video_title


def get_concepts_from_file(filename):
    if ".DS_Store" not in filename:
        with open(PATH_FOLDER_CONCEPTS + filename, "r") as lines:
            # Each file has only one line
            for line in lines:
                print line
                line = line.strip()
                # Mengdi's file came with those strange characters as separators
                concepts_info = line.split("\r")
                for concept_info in concepts_info:
                    # concept_name = concept_info[0]
                    concept_name = concept_info[:len(concept_info) - 1].strip()
                    # 0: prerequisite, 1: outcome
                    # concept_type = concept_info[1]
                    concept_type = concept_info[len(concept_info) - 1]
                    print concept_name + " " + concept_type
                    if concept_type == "0":
                        prerequisite_concepts.append(concept_name)
                    elif concept_type == "1":
                        outcome_concepts.append(concept_name)


if __name__ == '__main__':
    # When running locally, disable OAuthlib's HTTPs verification. When
    # running in production *do not* leave this option enabled.
    # os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
    # service = get_authenticated_service()
    # channels_list_by_username(service,
    #                           part='snippet,contentDetails,statistics',
    #                           forUsername='GoogleDevelopers')

    option = input("What action do you want to perform? [1: download video information, 2: enrich json with video transcripts, 3: re-rate video relevancy, 4: fix repeated phrases in the video transcripts]: ")

    reading_id = "iir"

    if option == 1:
        for filename in os.listdir(PATH_FOLDER_CONCEPTS):
            if reading_id in filename:
                #Need to restart the information related to the summary of video collection for that specific section
                summary_video_collection = {}
                prerequisite_concepts = []
                outcome_concepts = []
                results_folder = filename[:filename.index(".txt")]
                get_concepts_from_file(filename)

                # concepts = ["phrase query", "phrase index", "positional index", "implicit phrase query",
                #               "biword indexing model", "non-positional index", "compressed positional index"]
                # concepts = ["postings list intersection", "skip list", "skip list pointer", "skip span"]

                print outcome_concepts

                for i in range(0, len(outcome_concepts)):
                    concept1 = outcome_concepts[i]
                    query = concept1 + " " + GENERAL_TOPIC
                    args = prepare_search_args(query, MAX_RESULTS)
                    try:
                        print "Query: " + query
                        youtube_search(args, results_folder)
                    except HttpError, e:
                        print "An HTTP error %d occurred:\n%s" % (e.resp.status, e.content)

                    # Try queries with pair of concepts
                    for j in range(i + 1, len(outcome_concepts)):
                        concept2 = outcome_concepts[j]
                        # query = concept1
                        # if concept1 != concept2:
                        #    query = query + " " + concept2
                        query = concept1 + " " + concept2
                        args = prepare_search_args(query, MAX_RESULTS)
                        try:
                            print "Query: " + query
                            youtube_search(args, results_folder)
                        except HttpError, e:
                            print "An HTTP error %d occurred:\n%s" % (e.resp.status, e.content)
    if option == 2:
        for filename in os.listdir(PATH_FOLDER_CONCEPTS):
            if reading_id in filename:
                #Need to restart the information related to the summary of video collection for that specific section
                summary_video_collection = {}
                prerequisite_concepts = []
                outcome_concepts = []
                results_folder = filename[:filename.index(".txt")]
                print "Processing section "+results_folder
                with open(PATH_FOLDER_CONCEPTS + filename, "r") as lines:
                    # Each file has only one line
                    for line in lines:
                        print line
                        line = line.strip()
                        # Mengdi's file came with those strange characters as separators
                        concepts_info = line.split("\r")
                        for concept_info in concepts_info:
                            # concept_name = concept_info[0]
                            concept_name = concept_info[:len(concept_info) - 1].strip()
                            # 0: prerequisite, 1: outcome
                            # concept_type = concept_info[1]
                            concept_type = concept_info[len(concept_info) - 1]
                            print concept_name + " " + concept_type
                            if concept_type == "0":
                                prerequisite_concepts.append(concept_name)
                            elif concept_type == "1":
                                outcome_concepts.append(concept_name)
                for video_filename in os.listdir("./"+results_folder+"/"):
                    video_title = video_filename
                    if ".DS_Store" not in video_title and "summary_video_collection" not in video_title:
                        print "Processing: " + video_title
                        process_subtitles(results_folder, video_title)

    if option == 3:
        concept_embeddings = KeyedVectors.load("/Users/pawsres1/Documents/educational_videos/concept2vec.300.neg.2.epoch42.bin")
        file_relevant_videos = open("./relevant_videos.txt", "w")
        file_non_relevant_videos = open("./non_relevant_videos.txt", "w")
        file_no_concept_embeddings = open("./no_concept_embeddings.txt", "w")
        for filename in os.listdir(PATH_FOLDER_CONCEPTS):
            prerequisite_concepts = []
            outcome_concepts = []
            get_concepts_from_file(filename)
            for i in range(0,len(outcome_concepts)-1):
                concept_a = outcome_concepts[i]
                try:
                    vector_a = concept_embeddings[concept_a]
                    #print "Vector representation of concept " + concept_a
                    #print vector_a
                    for j in range(i+1,len(outcome_concepts)):
                        concept_b = outcome_concepts[j]
                        #print "Concept similarity between "+concept_a+" and "+concept_b
                        #concept_similarity = concept_embeddings.similarity(concept_a,concept_b)
                        #print concept_similarity
                except KeyError:
                    print concept_a+" not in concept embeddings"
                    file_no_concept_embeddings.write(concept_a+"\n")

            if reading_id in filename:
                file_relevant_videos.write(filename+"\n\n")
                file_non_relevant_videos.write(filename+"\n\n")
                #Need to restart the information related to the summary of video collection for that specific section
                summary_video_collection = {}
                results_folder = filename[:filename.index(".txt")]
                print "Results for " + results_folder
                num_relevant_videos = 0
                num_non_relevant_videos = 0
                for video_filename in os.listdir("./"+results_folder+"/"):
                    video_title = video_filename
                    if ".DS_Store" not in video_title:
                        if "summary_video_collection" not in video_title:
                            relevant_video = video_relevant_for_section(results_folder, video_title)
                            if relevant_video:
                                file_relevant_videos.write(video_title+"\n")
                                num_relevant_videos = num_relevant_videos + 1
                            else:
                                file_non_relevant_videos.write(video_title + "\n")
                                num_non_relevant_videos = num_non_relevant_videos + 1
                print "relevant videos: "+str(num_relevant_videos)
                print "non-relevant videos: "+str(num_non_relevant_videos)
            file_relevant_videos.write("\n")
            file_non_relevant_videos.write("\n")
        file_relevant_videos.close()
        file_non_relevant_videos.close()
        file_no_concept_embeddings.close()
    if option == 4:
        for filename in os.listdir(PATH_FOLDER_CONCEPTS):
            prerequisite_concepts = []
            outcome_concepts = []

            if reading_id in filename:
                results_folder = filename[:filename.index(".txt")]
                for video_filename in os.listdir("./"+results_folder+"/"):
                    video_title = video_filename
                    if ".DS_Store" not in video_title:
                        if "summary_video_collection" not in video_title:
                            fix_video_transcripts_from_timestamped_subtitles(results_folder, video_title)


