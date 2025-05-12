import requests
from bs4 import BeautifulSoup
from collections import defaultdict
import json
import string
import random
from pathlib import Path
from servertool import get_url_from_handle, load_servers
from playwright.async_api import async_playwright

# Global Variables
ratings = defaultdict(dict)
users_guilds = defaultdict(dict)
title_release_cache = {}  # cache to store already computed titles/release dates
servers = load_servers()


async def update_ratings(user, server_id):
    load_exisiting_ratings()
    await scrape_ratings(user, server_id)
    randomize_ratings_order(ratings)
    sort_by_most_watched(ratings)
    save_ratings(ratings)


async def get_html_with_playwright(url):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        await page.goto(url, timeout=60000)
        await page.wait_for_load_state("load")
        html = await page.content()
        await browser.close()
        return html


async def scrape_ratings(user, server_id):
    url = get_url_from_handle(user, server_id)
    if url is not None:
        html = await get_html_with_playwright(url)
        soup = BeautifulSoup(html, "lxml")
    else:
        print("User not found")
        return

    page_number = int(url.split("/")[-2])
    while True:
        film_logs = soup.find_all("li", class_="poster-container")
        if len(film_logs) == 0:
            print(f"{page_number} pages scraped")
            break

        print("Scraping page", page_number)
        for log in film_logs:
            try:
                extract_log_info(log, user, server_id)
            except IndexError:
                continue

        url = get_next_page(url)
        html = await get_html_with_playwright(url)
        soup = BeautifulSoup(html, "lxml")
        page_number += 1


### EXTRACTING INFORMATION FROM FILM PAGE ###


def extract_log_info(log, user, server_id):
    film_div = log.find("div", class_="film-poster")
    film_slug = film_div["data-film-slug"]

    # Follow the film URL and extract the full title from the film page
    film_url = "https://letterboxd.com/film/" + film_slug

    ## Load title and release date from cache if possible
    load_title_release_from_cache()
    if film_url in title_release_cache.keys():
        title = title_release_cache[film_url]["title"]
        release_year = title_release_cache[film_url]["release_year"]
        print("CACHE")
    else:
        title, release_year = extract_title_release_date(film_url)
        print("SCRAPE")

    full_title = title + " (" + release_year + ")"  # Combine title and release year
    rating = extract_rating(log)  # Extract rating

    print("Title:", full_title)
    print("Rating:", rating)
    print("URL:", film_url)
    print()

    # Save information to JSON file
    save_rating_info(full_title, rating, film_url, user, server_id)


def extract_title_release_date(film_url):
    # Extract title and release year from a film URL
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
    }
    film_response = requests.get(film_url, headers=headers)
    film_soup = BeautifulSoup(film_response.text, "lxml")
    title_soup = film_soup.find("title")
    if title_soup == None:
        return "No Title, No Year"
    title_with_info = title_soup.text
    title_parts = title_with_info.rsplit(
        " (", 1
    )  # Split into title and additional information
    title = remove_u200e(
        title_parts[0].strip()
    )  # Extract the title part and remove leading/trailing whitespaces

    release_year = ""
    if len(title_parts) > 1:
        release_year = title_parts[1].split(")")[0]

    title_release_cache[film_url] = {"title": title, "release_year": release_year}
    save_title_release_to_cache(title_release_cache)

    return title, release_year


def extract_rating(log):
    # Extract rating information from the <li> element
    rating_span = log.find("span", class_="rating")
    if rating_span:
        rating_class = rating_span["class"][-1]
        rating = int(rating_class.split("-")[-1])
    else:
        rating = None
    return rating


### SAVING INFORMATION ###


def save_rating_info(full_title, rating, film_url, user, guild_id):
    film_identifier = full_title.lower().replace(")", "").replace("(", "")

    if guild_id not in ratings:
        ratings[guild_id] = {}

    if film_identifier not in ratings[guild_id]:
        ratings[guild_id][film_identifier] = {
            "url": film_url,
            "title": full_title,
        }

    if rating is not None:
        ratings[guild_id][film_identifier][user] = rating
    else:
        ratings[guild_id][film_identifier][user] = "✓"


def save_ratings(ratings):
    with open("utils/ratings.json", "w") as file:
        json.dump(ratings, file, indent=2)


def load_title_release_from_cache():
    global title_release_cache
    try:
        with open("utils/cache.json", "r") as file:
            title_release_cache = json.load(file)
    except FileNotFoundError:
        pass


def save_title_release_to_cache(cache):
    with open("utils/cache.json", "w") as file:
        json.dump(cache, file, indent=2)


def load_exisiting_ratings(path="utils/ratings.json"):
    global ratings
    if Path(path).exists():
        with open(path, "r") as file:
            ratings = defaultdict(dict, json.load(file))


def remove_user_data(user, server_id):
    global ratings
    if server_id in ratings:
        for film in ratings[server_id]:
            if user in film:
                del film[user]

    save_ratings(ratings)


## OTHER HELPER FUNCTIONS ##


def remove_non_printable(text):
    printable_chars = set(string.printable)
    return "".join(filter(lambda x: x in printable_chars, text))


def get_next_page(url):
    # Get the URL for the next page of the user
    page_number = int(url.split("/")[-2])
    next_page_number = page_number + 1
    next_url = url.replace(f"/page/{page_number}/", f"/page/{next_page_number}/")
    return next_url


def remove_u200e(text):
    if text.startswith("\u200e"):
        return text[1:]  # Remove the first character
    return text


def randomize_dictionary_order(dictionary):
    keys = list(dictionary.keys())
    random.shuffle(keys)

    randomized_dict = {}
    for key in keys:
        randomized_dict[key] = dictionary[key]
    return randomized_dict


def randomize_ratings_order(ratings):
    ratings = randomize_dictionary_order(ratings)


def sort_by_most_watched(ratings):
    ## just sort a nested dictionary by the inner dictionary's length
    ratings = {
        k: v
        for k, v in sorted(ratings.items(), key=lambda item: len(item[1]), reverse=True)
    }


# if __name__ == "__main__":
#     update_ratings("lupsa", "644202189144850472")

# :)    :)    :)    :)    :)    :)    :)    :)    :)    :)
