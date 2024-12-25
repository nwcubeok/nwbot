import asyncio
import discord
import yt_dlp

def is_url(string: str) -> bool:
    """Détection ultra-simple pour savoir si c'est une URL ou non."""
    return string.startswith("http://") or string.startswith("https://")

async def play_song(guild_id: int, query: str, client, queues, voice_clients, ytdl=yt_dlp.YoutubeDL(), ffmpeg_options={}):
    """
    S'il s'agit d'une URL, on l'utilise directement.
    Sinon, on fait une recherche 'ytsearch:' sur YouTube.
    """
    loop = asyncio.get_running_loop()

    # -- 1) Vérifier si c'est un lien direct ou pas --
    if is_url(query):
        # Exemple : https://youtube.com/watch?v=XYZ...
        to_extract = query
    else:
        # Pas une URL -> recherche YouTube
        # ytsearch:<query> renvoie (en général) une liste d'entries dans data['entries']
        to_extract = f"ytsearch:{query}"

    # -- 2) Extraction des infos depuis yt-dlp --
    try:
        data = await loop.run_in_executor(
            None,
            lambda: ytdl.extract_info(to_extract, download=False)
        )
    except Exception as e:
        print(f"Erreur yt-dlp: {e}")
        return None

    # -- 3) Récupérer le "premier résultat" si c’est une recherche --
    if not is_url(query):
        # data['entries'] contient la liste des résultats
        if "entries" in data and data['entries']:
            data = data['entries'][0]  # on prend le premier
        else:
            print("Aucun résultat trouvé...")
            return None

    # data['url'] est le lien direct audio
    # data['title'] est le titre
    source = data["url"]
    title = data.get("title", "Titre inconnu")

    # -- 4) Lecture via FFmpegOpusAudio --
    player = discord.FFmpegOpusAudio(source, **ffmpeg_options)

    # -- 5) Callback de fin --
    def after_play(error):
        if error:
            print(f"Player error: {error}")
        # Quand la musique se termine, lancer la suivante dans la queue
        play_next_in_queue(guild_id, client, queues)

    voice_clients[guild_id].play(player, after=after_play)
    return title  # On renvoie le titre pour éventuellement l'afficher

def play_next_in_queue(guild_id: int, client, queues):
    """Vérifie la queue et lance le prochain morceau."""
    if queues[guild_id]:  # s'il reste des URLs/queries
        next_query = queues[guild_id].pop(0)
        future = asyncio.run_coroutine_threadsafe(
            play_song(guild_id, next_query),
            client.loop
        )
        try:
            future.result()
        except Exception as e:
            print(e)