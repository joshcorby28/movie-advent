import requests
import random
from calendar import monthrange
from datetime import datetime

API_KEY = "0583fddd4f95815a08d57376fe8bd414"

# Map months to seasonal themes
MONTH_THEME_MAP = {
    1: "Winter",
    2: "Winter",
    3: "Spring",
    4: "Spring",
    5: "Spring",
    6: "Summer",
    7: "Summer",
    8: "Summer",
    9: "Autumn",
    10: "Halloween",
    11: "Autumn",
    12: "Christmas"
}

# List of popular UK streaming services (TMDb provider IDs)
UK_SERVICES = {
    8: "Netflix",
    9: "Amazon Prime Video",
    337: "Disney+",
    2: "Apple TV",
    3: "Google Play Movies",
    68: "Microsoft Store"
}

def get_watch_providers(movie_id):
    """
    Fetch UK streaming providers for a given movie ID.
    """
    url = f"https://api.themoviedb.org/3/movie/{movie_id}/watch/providers?api_key={API_KEY}"
    response = requests.get(url).json()
    providers = response.get("results", {}).get("GB", {})
    flatrate = providers.get("flatrate", [])
    return [UK_SERVICES.get(provider["provider_id"], provider["provider_name"]) for provider in flatrate]

def fetch_streaming_movies(theme, min_count, category="all"):
    """
    Fetch movies that are on UK streaming services for a given theme.
    """
    movies = []
    seen_ids = set()
    page = 1
    current_year = datetime.now().year

    while len(movies) < min_count and page <= 10:  # limit pages to avoid excessive API calls
        url = f"https://api.themoviedb.org/3/search/movie?api_key={API_KEY}&query={theme}&page={page}&with_original_language=en"
        response = requests.get(url).json()
        results = response.get("results", [])
        if not results:
            break

        for movie in results:
            movie_id = movie["id"]
            if movie_id in seen_ids:
                continue

            # Filter by category
            year = movie.get("release_date", "1900")[:4]
            try:
                year = int(year)
            except ValueError:
                year = 1900

            if category == "modern" and year < current_year - 10:
                continue
            if category == "classics" and year >= current_year - 20:
                continue

            # Check if available on UK streaming services
            providers = get_watch_providers(movie_id)
            if not providers:
                continue  # skip if not on any UK service

            movies.append({
                "title": movie["title"],
                "release_date": movie.get("release_date", "Unknown"),
                "providers": providers
            })
            seen_ids.add(movie_id)

            if len(movies) >= min_count:
                break

        page += 1

    random.shuffle(movies)

    # If not enough movies, repeat list to fill the month
    while len(movies) < min_count:
        movies.extend(movies)

    return movies[:min_count]

def generate_monthly_streaming_list(month=None, category="all"):
    if month is None:
        month = datetime.now().month

    days_in_month = monthrange(datetime.now().year, month)[1]
    theme = MONTH_THEME_MAP.get(month, "Movies")
    print(f"Generating {days_in_month}-day streaming movie list for {theme} ({datetime.now().strftime('%B')}) - Category: {category}\n")
    return fetch_streaming_movies(theme, days_in_month, category)

if __name__ == "__main__":
    user_month = input("Enter month name (like 'October') or leave blank for current month: ").strip()
    user_category = input("Choose category (modern, classics, all): ").strip().lower()

    if user_month:
        try:
            month_number = datetime.strptime(user_month, "%B").month
        except ValueError:
            print("Invalid month name. Using current month instead.")
            month_number = datetime.now().month
    else:
        month_number = datetime.now().month

    if user_category not in ["modern", "classics", "all"]:
        user_category = "all"

    monthly_movies = generate_monthly_streaming_list(month_number, user_category)

    print("Your UK streaming movie list for the month:\n")
    for day, movie in enumerate(monthly_movies, 1):
        print(f"Day {day}: {movie['title']} ({movie['release_date']})")
        print(f"  Available on: {', '.join(movie['providers'])}\n")
