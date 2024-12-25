# main.py
import os
import asyncio
import random

import discord
import yt_dlp
from dotenv import load_dotenv

from modules.music import play_song, play_next_in_queue

def run_bot():
    load_dotenv()
    TOKEN = os.getenv('discord_token')

    hate_messages = [
        "tu crois tu parles à qui?",
        "ca va te foutre en slip tu crois quoi",
        "baisse les yeux",
        "ta gueule toi",
        "🤫",
        ":index_pointing_at_the_viewer: :joy_cat:"
    ]

    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)

    # Dictionnaires partagés par guilde
    queues = {}          # queues[guild_id] = liste d'URLs en attente
    voice_clients = {}   # voice_clients[guild_id] = objet VoiceClient
    current_track = {}   # current_track[guild_id] = URL en cours de lecture
    is_looping = {}      # is_looping[guild_id] = booléen (True si loop activé)
    skip_requested = {}  # skip_requested[guild_id] = booléen (True si skip demandé)

    # Prépare yt-dlp et ffmpeg
    yt_dl_options = {"format": "bestaudio/best"}
    ytdl = yt_dlp.YoutubeDL(yt_dl_options)

    ffmpeg_options = {
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
        'options': '-vn -filter:a "volume=0.25"'
    }

    @client.event
    async def on_ready():
        print(f"{client.user} is now jamming!")

    @client.event
    async def on_message(message):
        if message.author == client.user:
            return

        if message.author.id == 290159614995988481 and message.content.startswith("?"):
            return await message.channel.send(random.choice(hate_messages))

        # Initialiser les clés pour cette guilde si pas encore fait
        if message.guild and message.guild.id not in queues:
            queues[message.guild.id] = []
            voice_clients[message.guild.id] = None
            current_track[message.guild.id] = None
            is_looping[message.guild.id] = False
            skip_requested[message.guild.id] = False

        #
        # Commande ?play
        #
        if message.content.startswith("?play"):
            print(f"Guild {message.guild.id} - Playing {current_track[message.guild.id]}")
            if not message.author.voice or not message.author.voice.channel:
                await message.channel.send("Rejoins un salon vocal pour jouer de la musique.")
                return

            # Extraire la "query"
            parts = message.content.split(maxsplit=1)
            if len(parts) < 2:
                await message.channel.send("Utilisation : `?play <URL ou recherche>`")
                return
            query = parts[1]  # peut être "rick astley never gonna give you up" ou un lien

            # Se connecter au salon si pas déjà fait
            if voice_clients[message.guild.id] is None or not voice_clients[message.guild.id].is_connected():
                try:
                    voice_client = await message.author.voice.channel.connect()
                    voice_clients[message.guild.id] = voice_client
                except Exception as e:
                    print(e)
                    return

            vc = voice_clients[message.guild.id]
            if vc.is_playing():
                # Ajouter à la queue
                queues[message.guild.id].append(query)
                await message.add_reaction("➕")
            else:
                # Jouer immédiatement
                title_played = await play_song(message.guild.id, query, client, queues, voice_clients, ytdl, ffmpeg_options)
                if title_played:
                    current_track[message.guild.id] = title_played
                    await message.add_reaction("▶️")
                    await message.channel.send(f"Lecture : **{title_played}**")

        #
        # Commande ?pause
        #
        elif message.content.startswith("?pause"):
            vc = voice_clients.get(message.guild.id)
            if vc and vc.is_playing():
                vc.pause()
                await message.add_reaction("⏸️")

        #
        # Commande ?resume
        #
        elif message.content.startswith("?resume"):
            vc = voice_clients.get(message.guild.id)
            if vc and vc.is_paused():
                vc.resume()
                await message.add_reaction("⏯️")

        #
        # Commande ?queue
        #
        elif message.content.startswith("?queue"):
            if not queues[message.guild.id]:
                if current_track[message.guild.id]:
                    await message.channel.send(f"**En cours de lecture :** {current_track[message.guild.id]} \n\nLa file d'attente est vide.")
                else:
                    await message.channel.send("La file d'attente est vide.")
            else:
                queue_list = []
                for i, url in enumerate(queues[message.guild.id], start=1):
                    queue_list.append(f"{i}. {url}")
                queue_str = "\n".join(queue_list)
                await message.channel.send(f"**File d'attente :**\n{queue_str}")

        #
        # Commande ?stop
        #
        elif message.content.startswith("?stop"):
            vc = voice_clients.get(message.guild.id)
            if vc:
                # On nettoie la file d'attente
                queues[message.guild.id].clear()
                # On stoppe la musique
                if vc.is_playing() or vc.is_paused():
                    vc.stop()
                # Déconnexion
                if vc.is_connected():
                    await vc.disconnect()
                    voice_clients[message.guild.id] = None
                await message.add_reaction("⏹️")
            else:
                await message.add_reaction("🤬")

        #
        # Commande ?loop : Active/désactive la boucle sur la musique en cours
        #
        elif message.content.startswith("?loop"):
            g_id = message.guild.id
            is_looping[g_id] = not is_looping[g_id]
            if is_looping[g_id]:
                await message.add_reaction("🔁")
            else:
                await message.add_reaction("➡️")

        #
        # Commande ?skip : Passe au morceau suivant
        #
        elif message.content.startswith("?skip"):
            g_id = message.guild.id
            vc = voice_clients.get(g_id)
            if vc and (vc.is_playing() or vc.is_paused()):
                # On signale qu'un skip est demandé
                skip_requested[g_id] = True
                vc.stop()  # Déclenche after_play -> on passera au suivant
                await message.add_reaction("⏭️")
            else:
                await message.add_reaction("🤨")

    client.run(TOKEN)
