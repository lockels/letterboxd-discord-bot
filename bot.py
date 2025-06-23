# Libraries
from discord.ext import commands
import discord
import random
from bs4 import BeautifulSoup as bs
import requests
import json
from pathlib import Path
import webserver
import os
from dotenv import load_dotenv

## Local imports
import rating_updates
from servertool import delete_user, insert_user, load_servers, add_server

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
general = 775154916465442878
botGeneral = 1060040818653659170
bot = commands.Bot(command_prefix="-", intents=discord.Intents.all())


@bot.event
async def on_ready():
    # await scrape_user_messages(general, 85614143951892480)
    print("BOT IS READY")
    await sync_commands()


async def sync_commands():
    try:
        synced = await bot.tree.sync()
        print(f"Synced: {len(synced)} commands")
    except Exception as e:
        print(f"Failed to sync: {e}")


def open_ratings(path="utils/ratings.json"):
    if Path(path).exists():
        with open(path) as f:
            return json.load(f)
    return {}


def open_quotes(path="utils/quotes.txt"):
    if Path(path).exists():
        with open(path) as f:
            return f.readlines()
    return []


@bot.command()
async def about(ctx):
    await ctx.send(
        """Greetings! I was coded for this server, Thru The Lens, using
        Javascript to help serve certain command needs that cannot be
        fulfilled by our other bots. I offer mostly Letterboxd-based
        commands. I was coded by fresh kitty, and I was first fired up on
        July 28, 2020!"""
    )


@bot.command()
async def inspire(ctx):
    quotes = open_quotes()
    quote = random.choice(quotes)
    await ctx.send(quote)


def partial_key_search(ratings, server_id, film):
    filminfo = ""
    for key in ratings[server_id]:
        if key.startswith(film.lower()):
            filminfo = ratings[server_id][key]
    return filminfo


def calculate_avg(filminfo):
    num_unrated, sum, avg = 0, 0, 0
    for user, rating in filminfo.items():
        if user == "url" or user == "title":
            num_unrated += 1
            continue
        elif rating == "✓":
            num_unrated += 1
            continue
        sum += rating
    if num_unrated == len(filminfo):
        pass
    else:
        avg = round(sum / (len(filminfo) - num_unrated), 2)
    return avg


def format_ratings(filminfo):
    ratings = ""
    for user, rating in filminfo.items():
        if user == "url" or user == "title":  # skip url and title entries
            continue
        elif rating == "✓":
            continue
        ratings += f"{user}: {rating}\n"
    return ratings


@bot.tree.command(name="add")
async def add_user(interaction: discord.Interaction, letterboxd_handle: str):
    assert interaction.guild is not None

    server_id = str(interaction.guild.id)
    servers = load_servers()
    user = interaction.user.name

    if server_id not in servers:
        add_server(servers, server_id)

    if user in servers[server_id]:
        await interaction.response.send_message(f"{user} is already registered")
        return

    insert_user(servers, interaction.user.name, letterboxd_handle, server_id)
    await rating_updates.update_ratings(letterboxd_handle, server_id)
    await interaction.response.send_message(
        f"Added {letterboxd_handle} to {user}'s account. You can now use the bot!"
    )


@bot.tree.command(name="delete")
async def remove_user(interaction: discord.Interaction):
    assert interaction.guild is not None

    server_id = str(interaction.guild.id)
    servers = load_servers()
    user = interaction.user.name

    if server_id not in servers:
        await interaction.response.send_message("No users registered for this server")
        return

    if user not in servers[server_id]:
        await interaction.response.send_message(f"{user} is not registered")
        return

    delete_user(servers, user, server_id)
    await interaction.response.send_message(f"Removed {user} from the server")
    return


@bot.tree.command(name="avg")
async def server_avg(interaction: discord.Interaction, film: str):
    assert interaction.guild is not None

    ratings = open_ratings()
    server_id = str(interaction.guild.id)

    filminfo = 0, ""
    try:  # try a full key match first
        filminfo = ratings[server_id][film.lower()]

    except KeyError:  # searching with partial key. use tries later maybe?
        filminfo = partial_key_search(ratings, server_id, film)
    if filminfo == "":
        await interaction.response.send_message("Nobody has rated this movie")
        return
    avg = calculate_avg(filminfo)
    ratings = format_ratings(filminfo)
    embed = discord.Embed(
        title=f"Ratings for {filminfo['title']}",
        url=f"{filminfo['url']}",
        description=f"{ratings}",
    )
    embed.set_footer(text=f"Server Average: {avg}, from {len(filminfo) - 2} members")
    embed.set_thumbnail(url=getimg(f"{filminfo['url']}"))

    await interaction.response.send_message(embed=embed)


def calculate_top_films(ratings, threshold):
    films = []
    for film in ratings:
        filminfo = ratings[film]
        total_watched = len(filminfo) - 2
        if total_watched >= threshold:
            avg = calculate_avg(filminfo)
            title, url = filminfo["title"], filminfo["url"]
            films.append((title, avg, total_watched, url))

    return films


@bot.tree.command(name="top")
async def top(interaction: discord.Interaction, num_members: int):
    ratings = open_ratings()
    films = calculate_top_films(ratings, 5)

    sorted_films = sorted(films, key=lambda film: film[1], reverse=True)
    sorted_films = sorted_films[:25]

    description = ""
    index = 1
    for film in sorted_films:
        description += (
            f"{index}: [{film[0]}]({film[3]}) {film[1]}, by {film[2]} members\n"
        )
        index += 1

    embed = discord.Embed(
        title=f"Top 25 films seen by {num_members} or more members",
        description=description,
    )
    await interaction.response.send_message(embed=embed)


@bot.command()
async def update(ctx, user):
    server_id = str(ctx.guild.id)
    servers = load_servers()

    if server_id not in servers:
        await ctx.send("No users registered for this server")
        return

    server_users = servers[server_id]

    ## Everyone
    if user == "everyone":
        if ctx.author.id != 1019951678260248606:
            await ctx.send("You are not allowed to do this")
            return
        await ctx.send("Updating everyone")
        for account in server_users:
            await run_update(ctx, account)
        ## Single user
    else:
        if user in server_users:
            await run_update(ctx, user)
        else:
            await ctx.send("User not found")


async def run_update(ctx, account):
    await ctx.send(f"Updating {account}")
    await rating_updates.update_ratings(account, str(ctx.guild.id))
    await ctx.send(f"Done updating {account}")


def getimg(url):
    r = requests.get(url)
    soup = bs(r.text, "lxml")  # lxml parser to make faster.... still slow as fuck
    script_w_data = soup.select_one('script[type="application/ld+json"]')
    if script_w_data == None:
        return
    json_obj = json.loads(script_w_data.text.split(" */")[1].split("/* ]]>")[0])
    return json_obj["image"]


if __name__ == "__main__":
    bot.run(BOT_TOKEN)
    webserver.keep_alive()
