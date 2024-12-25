import asyncio
import discord
import yt_dlp

def is_url(string: str) -> bool:
    """Détection ultra-simple pour savoir si c'est une URL ou non."""
    return string.startswith("http://") or string.startswith("https://")

async def fetch_track_info(query: str, ytdl) -> dict:
    """
    Récupère, via yt-dlp, un dict contenant :
      { "title": <titre>, "source": <lien audio> }
    Ou None si échec ou pas de résultat.
    """
    loop = asyncio.get_running_loop()

    # 1) Vérifier si c'est un lien direct ou pas
    to_extract = query if is_url(query) else f"ytsearch:{query}"

    # 2) Extraction des infos
    try:
        data = await loop.run_in_executor(
            None,
            lambda: ytdl.extract_info(to_extract, download=False)
        )
    except Exception as e:
        print(f"Erreur yt-dlp: {e}")
        return None

    # 3) Si c'était une recherche, on prend la 1ère entrée
    if not is_url(query):
        if "entries" in data and data["entries"]:
            data = data["entries"][0]
        else:
            print("Aucun résultat trouvé...")
            return None

    
    # 4) Construire le dictionnaire
    source = data["url"] 
    title = data.get("title", "Titre inconnu")
    video_url = data["webpage_url"] if "webpage_url" in data else query

    return { "title": title, "source": source, "url": video_url } 


async def play_song(
    guild_id: int,
    track_info: dict,
    client,
    queues,
    voice_clients,
    current_track,
    ffmpeg_options={}
):
    """
    Joue un 'track_info' = { 'title': str, 'source': str } sur le voice_client
    Puis appelle le morceau suivant s'il existe.
    """
    vc = voice_clients[guild_id]
    source = track_info["source"]
    title = track_info["title"]

    player = discord.FFmpegOpusAudio(source, **ffmpeg_options)

    def after_play(error):
        if error:
            print(f"Player error: {error}")

        # On passe au morceau suivant
        play_next_in_queue(guild_id, client, queues, voice_clients, current_track, ffmpeg_options)

    # Mettre à jour current_track si besoin
    current_track[guild_id] = track_info

    vc.play(player, after=after_play)
    return title  # On renvoie le titre si on veut l’afficher

def play_next_in_queue(
    guild_id: int,
    client,
    queues,
    voice_clients,
    current_track,
    ffmpeg_options
):
    """
    Vérifie la file d'attente et lance le prochain morceau s'il y en a un.
    Si plus rien, current_track[guild_id] = None
    """
    if queues[guild_id]:
        next_track = queues[guild_id].pop(0)  # next_track est un dict {title, source}
        future = asyncio.run_coroutine_threadsafe(
            play_song(
                guild_id=guild_id,
                track_info=next_track,
                client=client,
                queues=queues,
                voice_clients=voice_clients,
                current_track=current_track,
                ffmpeg_options=ffmpeg_options
            ),
            client.loop
        )
        try:
            future.result()
        except Exception as e:
            print(e)
    else:
        # Plus rien dans la queue
        current_track[guild_id] = None