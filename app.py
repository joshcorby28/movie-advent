from flask import Flask, render_template, request, jsonify
from datetime import datetime
from calendar import monthrange
import requests
import random
import time
import os

app = Flask(__name__)

API_KEY = os.environ.get('TMDB_API_KEY', '0583fddd4f95815a08d57376fe8bd414')

MONTH_THEME_MAP = {
    1: "Winter", 2: "Winter", 3: "Spring", 4: "Spring", 5: "Spring",
    6: "Summer", 7: "Summer", 8: "Summer", 9: "Autumn", 10: "Halloween",
    11: "Autumn", 12: "Christmas"
}

THEME_GENRE_MAP = {
    "Halloween": 27,  # Horror
    "Christmas": 10751,  # Family
    "Winter": None,
    "Spring": None,
    "Summer": None,
    "Autumn": None,
    "Movies": None
}

THEME_KEYWORD_MAP = {
    "Christmas": 207317,  # Christmas
    "Halloween": 616,  # Halloween
}

# Only Netflix, Amazon Prime, Disney+
UK_SERVICES = [8, 9, 337]
UK_SERVICE_NAMES = {
    8: "Netflix",
    9: "Amazon Prime Video",
    337: "Disney+",
    531: "Paramount+",
    350: "Apple TV+"
}

def fetch_streaming_movies(theme, min_count, category="all", genre=None, min_rating="", year_from="", year_to="", exclude_titles=[], only_streaming=True, services=['8','9','337']):
    print(f"Fetching movies with theme: {theme}, min_count: {min_count}, category: {category}")
    movies = []
    seen_ids = set()
    current_year = datetime.now().year
    random.seed(time.time())
    page = 1
    page_limit = 5 if min_count == 1 or not only_streaming else 3
    if min_count == 1:
        sort_by = "vote_average.desc"
    else:
        sort_by = random.choice(['popularity.desc', 'vote_average.desc', 'release_date.desc'])

    while len(movies) < min_count and page <= page_limit:  # limit pages for speed
        providers_part = ""
        url = (
            "https://api.themoviedb.org/3/discover/movie"
            f"?api_key={API_KEY}"
            "&language=en-US"
            "&with_original_language=en"
            "&with_runtime.gte=60"
            f"&sort_by={sort_by}"
            f"{providers_part}"
            f"&page={page}"
        )
        keyword = THEME_KEYWORD_MAP.get(theme)
        if keyword:
            url += f"&with_keywords={keyword}"
        if genre:
            url += f"&with_genres={genre}"
        else:
            genre = THEME_GENRE_MAP.get(theme)
            if genre:
                url += f"&with_genres={genre}"
            elif theme != "Movies" and not keyword:
                url += f"&query={theme}"

        if min_rating:
            url += f"&vote_average.gte={min_rating}"
        if year_from:
            url += f"&primary_release_date.gte={year_from}-01-01"
        if year_to:
            url += f"&primary_release_date.lte={year_to}-12-31"
        print(f"Requesting URL: {url}")
        response = requests.get(url)
        print(f"Response status: {response.status_code}")
        if response.status_code != 200:
            print(f"API error: {response.text}")
            break
        response_json = response.json()
        print(f"Response keys: {list(response_json.keys())}")
        results = response_json.get("results", [])
        print(f"Results count: {len(results)}")
        if not results:
            break

        for movie in results:
            movie_id = movie["id"]
            if movie_id in seen_ids:
                continue
            if movie["title"] in exclude_titles:
                continue

            year = movie.get("release_date", "1900")[:4]
            try:
                year = int(year)
            except ValueError:
                year = 1900

            if year > current_year:
                continue
            if category == "modern" and year < current_year - 10:
                continue
            if category == "classics" and year >= current_year - 20:
                continue

            # Fetch watch providers for this movie
            providers_url = f"https://api.themoviedb.org/3/movie/{movie_id}/watch/providers?api_key={API_KEY}"
            print(f"Fetching providers for movie {movie_id}: {providers_url}")
            providers_response = requests.get(providers_url)
            print(f"Providers response status: {providers_response.status_code}")
            if providers_response.status_code != 200:
                print(f"Failed to get providers for {movie_id}")
                continue  # Skip if can't get providers
            providers_data = providers_response.json()
            providers_list = providers_data.get("results", {}).get("US", {}).get("flatrate", [])
            if only_streaming and not any(str(p["provider_id"]) in services for p in providers_list):
                continue
            providers = [UK_SERVICE_NAMES.get(p["provider_id"], p["provider_name"]) for p in providers_list if str(p["provider_id"]) in services]
            print(f"Providers for {movie_id}: {providers}")

            movies.append({
                "title": movie["title"],
                "release_date": movie.get("release_date", "Unknown"),
                "providers": providers,
                "poster_path": movie.get("poster_path")
            })
            seen_ids.add(movie_id)

            if len(movies) >= min_count:
                break

        page += 1

    if len(movies) <= min_count:
        return movies
    else:
        return random.sample(movies, min_count)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/get_movies", methods=["POST"])
def get_movies():
    print("Received request for get_movies")
    data = request.get_json()  # Get JSON from AJAX
    print(f"Data received: {data}")
    month_name = data.get("month", "")
    theme_input = data.get("theme", "")
    category = data.get("category", "all")

    if theme_input:
        theme = theme_input
        min_count = 31  # Fixed for theme selection
        display_month = f"Theme: {theme}"
    else:
        try:
            month_number = datetime.strptime(month_name, "%B").month
            print(f"Parsed month: {month_name} to {month_number}")
        except Exception as e:
            print(f"Error parsing month: {e}")
            month_number = datetime.now().month

        days_in_month = monthrange(datetime.now().year, month_number)[1]
        theme = MONTH_THEME_MAP.get(month_number, "Movies")
        min_count = days_in_month
        display_month = month_name or "Current Month"

    genre_input = data.get("genre", "")
    genre = genre_input if genre_input else None
    year_from = data.get("year_from", "")
    year_to = data.get("year_to", "")
    print(f"Fetching movies for theme: {theme}, genre: {genre}, year_from: {year_from}, year_to: {year_to}, min_count: {min_count}, category: {category}")
    only_streaming = data.get('only_streaming', True)
    exclude_titles = []
    movies = fetch_streaming_movies(theme, min_count, category, genre, '', year_from, year_to, exclude_titles, only_streaming, data)
    print(f"Fetched {len(movies)} movies")

    message = ""
    if len(movies) < min_count:
        message = f"There are only {len(movies)} movies matching your criteria. Please adjust the filters (e.g., year range or genre) to find more results."

    return jsonify({"movies": movies, "month": display_month, "category": category, "message": message})


@app.route("/get_replacement_movie", methods=["POST"])
def get_replacement_movie():
    data = request.get_json()
    print(f"Replacement request data: {data}")
    month_name = data.get("month", "")
    theme_input = data.get("theme", "")
    genre_input = data.get("genre", "")
    category = data.get("category", "all")
    min_rating = data.get("min_rating", "")
    year_from = data.get("year_from", "")
    year_to = data.get("year_to", "")
    exclude_titles = data.get("current_titles", [])
    print(f"Exclude titles: {exclude_titles}")

    genre = genre_input if genre_input else None
    if theme_input:
        theme = theme_input
        min_count = 1
    else:
        try:
            month_number = datetime.strptime(month_name, "%B").month
        except Exception as e:
            month_number = datetime.now().month
        days_in_month = monthrange(datetime.now().year, month_number)[1]
        theme = MONTH_THEME_MAP.get(month_number, "Movies")
        min_count = 1

    only_streaming = data.get('only_streaming', True)
    movies = fetch_streaming_movies(theme, min_count, category, genre, '', year_from, year_to, exclude_titles, only_streaming, data)
    print(f"Replacement movies fetched: {len(movies)}")
    if movies:
        print(f"Selected replacement movie: {movies[0]['title']}")
        return jsonify({"movie": movies[0]})
    else:
        return jsonify({"error": "No replacement movie found"}), 404


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)
