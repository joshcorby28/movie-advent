import logging
logging.basicConfig(level=logging.DEBUG)

from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from calendar import monthrange
import requests
import random
import time
import os
import json

app = Flask(__name__)
logging.info("Flask app created")
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///movie_advent.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
logging.info("Database initialized")
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

API_KEY = os.environ.get('TMDB_API_KEY', '0583fddd4f95815a08d57376fe8bd414')

MONTH_THEME_MAP = {
    1: "Winter", 2: "Winter", 3: "Spring", 4: "Spring", 5: "Spring",
    6: "Summer", 7: "Summer", 8: "Summer", 9: "Autumn", 10: "Halloween",
    11: "Autumn", 12: "Christmas"
}

THEME_GENRE_MAP = {
    "Halloween": None,  # Any genre for Halloween
    "Christmas": 10751,  # Family
    "Winter": None,
    "Spring": None,
    "Summer": None,
    "Autumn": None,
    "Movies": None
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

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(150), nullable=False)
    movie_lists = db.relationship('MovieList', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class MovieList(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    movies = db.Column(db.Text, nullable=False)  # JSON string of movies
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if User.query.filter_by(username=username).first():
            flash('Username already exists')
            return redirect(url_for('register'))
        user = User(username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        return redirect(url_for('index'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('index'))
        flash('Invalid username or password')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

def get_theme_keywords(theme):
    """Fetch keyword IDs for a given theme"""
    
    # Special handling for Halloween with specific keywords
    if theme == "Halloween":
        specific_keywords = ["halloween", "slasher", "scary", "paranormal", "jumpscare", "supernatural horror", "demonic"]
        keyword_ids = []
        
        for kw in specific_keywords:
            url = f"https://api.themoviedb.org/3/search/keyword?api_key={API_KEY}&query={kw}"
            response = requests.get(url)
            if response.status_code == 200:
                data = response.json()
                results = data.get("results", [])
                if results:
                    # Take the first (most relevant) match
                    kid = results[0]["id"]
                    keyword_ids.append(kid)
                    print(f"Added Halloween keyword '{kw}' (ID: {kid})")
                else:
                    print(f"No keyword found for '{kw}'")
            else:
                print(f"Failed to fetch keyword for '{kw}': {response.text}")
            time.sleep(0.1)  # Small delay to avoid rate limits
        
        print(f"Halloween keywords found: {len(keyword_ids)} IDs: {keyword_ids}")
        return keyword_ids if keyword_ids else [616]  # 616 is a fallback Halloween keyword ID
    
    # For Christmas, use specific keywords too
    elif theme == "Christmas":
        specific_keywords = ["christmas", "santa claus", "holiday", "xmas"]
        keyword_ids = []
        
        for kw in specific_keywords:
            url = f"https://api.themoviedb.org/3/search/keyword?api_key={API_KEY}&query={kw}"
            response = requests.get(url)
            if response.status_code == 200:
                data = response.json()
                results = data.get("results", [])
                if results:
                    kid = results[0]["id"]
                    keyword_ids.append(kid)
                    print(f"Added Christmas keyword '{kw}' (ID: {kid})")
            else:
                print(f"Failed to fetch keyword for '{kw}'")
            time.sleep(0.1)
        
        print(f"Christmas keywords found: {len(keyword_ids)} IDs: {keyword_ids}")
        return keyword_ids if keyword_ids else [207]  # 207 is a fallback Christmas keyword ID
    
    # For other themes, do a general keyword search
    else:
        query = theme.lower()
        url = f"https://api.themoviedb.org/3/search/keyword?api_key={API_KEY}&query={query}"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            keywords = data.get("results", [])
            # Take top 5-10 keywords related to the theme
            keyword_ids = [kw["id"] for kw in keywords[:10]]
            print(f"Fetched keywords for {theme}: {[kw['name'] for kw in keywords[:10]]}")
            return keyword_ids
        else:
            print(f"Failed to fetch {theme} keywords: {response.text}")
            return []

def fetch_streaming_movies(theme, min_count, category="all", genre=None, year_from="", year_to="", exclude_titles=[], only_streaming=True, selected_services=None):
    selected_services = selected_services or ['8','9','337']  # Netflix, Prime, Disney+
    print(f"DEBUG: Fetching movies with theme: {theme}, min_count: {min_count}, category: {category}")

    movies = []
    seen_ids = set()
    current_year = datetime.now().year
    page = 1
    max_pages = 50  # don't hammer all 500

    # Sorting options for variety
    if theme == "Movies":
        sort_options = ['popularity.desc', 'release_date.desc', 'vote_average.desc']
    else:
        sort_options = ['popularity.desc']

    # Special case: General Movies
    if theme == "Movies":
        while len(movies) < min_count and page <= max_pages:
            sort_by = random.choice(sort_options)

            url = (
                f"https://api.themoviedb.org/3/discover/movie?"
                f"api_key={API_KEY}&language=en-US&region=GB"
                f"&sort_by={sort_by}&include_adult=false&include_video=false"
                f"&with_watch_providers={'|'.join(selected_services)}"
                f"&watch_region=GB&page={page}&vote_count.gte=500&with_runtime.gte=60&with_original_language=en"
            )
            if genre:
                url += f"&with_genres={genre}"
            if year_from:
                url += f"&primary_release_date.gte={year_from}-01-01"
            if year_to:
                url += f"&primary_release_date.lte={year_to}-12-31"

            resp = requests.get(url)
            if resp.status_code != 200:
                print(f"Discover API error: {resp.text}")
                break

            results = resp.json().get("results", [])
            for movie in results:
                movie_id = movie["id"]
                if movie_id in seen_ids or movie["title"] in exclude_titles:
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

                movies.append({
                    "title": movie["title"],
                    "release_date": movie.get("release_date", "Unknown"),
                    "poster_path": movie.get("poster_path"),
                    "providers": [UK_SERVICE_NAMES.get(int(sid), sid) for sid in selected_services]
                })
                seen_ids.add(movie_id)

                if len(movies) >= min_count:
                    break

            page += 1

        random.shuffle(movies)
        return movies[:min_count]

    # --- Themed movie logic using DISCOVER endpoint with keywords ---
    else:
        # Get keyword IDs for the theme
        keyword_ids = get_theme_keywords(theme)
        if not keyword_ids:
            print(f"No keywords found for theme {theme}, using search fallback")
            keyword_string = None
        else:
            # Use pipe (OR) separator for broader results
            keyword_string = "|".join(map(str, keyword_ids))
            print(f"Using keywords for {theme}: {keyword_string}")
        
        while len(movies) < min_count and page <= max_pages:
            # Use discover endpoint with keywords
            url = (
                f"https://api.themoviedb.org/3/discover/movie?"
                f"api_key={API_KEY}&language=en-US&region=GB"
                f"&sort_by=popularity.desc&include_adult=false&include_video=false"
                f"&with_watch_providers={'|'.join(selected_services)}"
                f"&watch_region=GB&page={page}&vote_count.gte=100"
            )
            
            # Add keywords if available
            if keyword_string:
                url += f"&with_keywords={keyword_string}"
            
            # Add genre if specified
            if genre:
                url += f"&with_genres={genre}"
            
            # Add year filters
            if year_from:
                url += f"&primary_release_date.gte={year_from}-01-01"
            if year_to:
                url += f"&primary_release_date.lte={year_to}-12-31"

            resp = requests.get(url)
            if resp.status_code != 200:
                print(f"Discover API error for theme {theme}: {resp.text}")
                break

            results = resp.json().get("results", [])
            
            if not results and page == 1:
                print(f"No results for {theme} with keywords, trying without")
                # Retry without keywords if first page has no results
                if keyword_string:
                    url = url.replace(f"&with_keywords={keyword_string}", "")
                    resp = requests.get(url)
                    if resp.status_code == 200:
                        results = resp.json().get("results", [])
            
            for movie in results:
                movie_id = movie["id"]
                if movie_id in seen_ids or movie["title"] in exclude_titles:
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

                movies.append({
                    "title": movie["title"],
                    "release_date": movie.get("release_date", "Unknown"),
                    "poster_path": movie.get("poster_path"),
                    "providers": [UK_SERVICE_NAMES.get(int(sid), sid) for sid in selected_services]
                })
                seen_ids.add(movie_id)

                if len(movies) >= min_count:
                    break

            page += 1

        random.shuffle(movies)
        return movies[:min_count]


@app.route("/")
def index():
    return render_template("index.html", user=current_user)


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
    selected_services = data.get('services', ['8','9','337'])
    movies = fetch_streaming_movies(theme, min_count, category, genre, year_from, year_to, exclude_titles, only_streaming, selected_services)
    print(f"Fetched {len(movies)} movies")

    message = ""
    if len(movies) < min_count:
        message = f"There are only {len(movies)} movies matching your criteria. Please adjust the filters (e.g., year range or genre) to find more results."

    return jsonify({"movies": movies, "month": display_month, "category": category, "message": message})


def fetch_single_replacement_movie(theme, category, genre, year_from, year_to, exclude_titles, only_streaming, selected_services):
    current_year = datetime.now().year

    # Use discover for all movies (general and themed)
    if theme == "Movies":
        # General movies - use broad discover
        url = (
            f"https://api.themoviedb.org/3/discover/movie?api_key={API_KEY}"
            f"&language=en-US&region=GB&include_adult=false&include_video=false"
            f"&sort_by=popularity.desc&vote_count.gte=500&with_runtime.gte=60&with_original_language=en"
            f"&with_watch_providers={'|'.join(selected_services)}"
            f"&watch_region=GB"
        )
    else:
        # Themed movies - use discover with keywords
        keyword_ids = get_theme_keywords(theme)
        keyword_string = "|".join(map(str, keyword_ids)) if keyword_ids else None
        
        url = (
            f"https://api.themoviedb.org/3/discover/movie?api_key={API_KEY}"
            f"&language=en-US&region=GB&include_adult=false&include_video=false"
            f"&sort_by=popularity.desc&vote_count.gte=100"
            f"&with_watch_providers={'|'.join(selected_services)}"
            f"&watch_region=GB"
        )
        
        if keyword_string:
            url += f"&with_keywords={keyword_string}"

    if genre:
        url += f"&with_genres={genre}"
    if year_from:
        url += f"&primary_release_date.gte={year_from}-01-01"
    if year_to:
        url += f"&primary_release_date.lte={year_to}-12-31"

    response = requests.get(url)
    if response.status_code != 200:
        print(f"Discover API error: {response.text}")
        return None

    results = response.json().get("results", [])
    random.shuffle(results)  # Randomize order

    for movie in results:
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

        # Movie is already filtered by streaming services in discover endpoint
        return {
            "title": movie["title"],
            "release_date": movie.get("release_date", "Unknown"),
            "providers": [UK_SERVICE_NAMES.get(int(sid), sid) for sid in selected_services],
            "poster_path": movie.get("poster_path")
        }
    
    return None

@app.route("/get_replacement_movie", methods=["POST"])
def get_replacement_movie():
    data = request.get_json()
    print(f"Replacement request data: {data}")
    month_name = data.get("month", "")
    theme_input = data.get("theme", "")
    genre_input = data.get("genre", "")
    category = data.get("category", "all")
    year_from = data.get("year_from", "")
    year_to = data.get("year_to", "")
    exclude_titles = data.get("current_titles", [])
    print(f"Exclude titles: {exclude_titles}")

    genre = genre_input if genre_input else None
    if theme_input:
        theme = theme_input
    else:
        try:
            month_number = datetime.strptime(month_name, "%B").month
        except Exception as e:
            month_number = datetime.now().month
        theme = MONTH_THEME_MAP.get(month_number, "Movies")

    only_streaming = data.get('only_streaming', True)
    selected_services = data.get('services', ['8','9','337'])
    movie = fetch_single_replacement_movie(theme, category, genre, year_from, year_to, exclude_titles, only_streaming, selected_services)
    if movie:
        print(f"Selected replacement movie: {movie['title']}")
        return jsonify({"movie": movie})
    else:
        return jsonify({"error": "No replacement movie found"}), 404

@app.route('/save_list', methods=['POST'])
@login_required
def save_list():
    data = request.get_json()
    name = data.get('name', 'My Movie List')
    movies = data.get('movies', [])
    movie_list = MovieList(name=name, movies=json.dumps(movies), user_id=current_user.id)
    db.session.add(movie_list)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/my_lists')
@login_required
def my_lists():
    lists = MovieList.query.filter_by(user_id=current_user.id).order_by(MovieList.created_at.desc()).all()
    for lst in lists:
        lst.parsed_movies = json.loads(lst.movies)
    return render_template('my_lists.html', lists=lists)

@app.route('/delete_list', methods=['POST'])
@login_required
def delete_list():
    data = request.get_json()
    list_id = data.get('id')
    movie_list = MovieList.query.filter_by(id=list_id, user_id=current_user.id).first()
    if movie_list:
        db.session.delete(movie_list)
        db.session.commit()
        return jsonify({'success': True})
    else:
        return jsonify({'error': 'List not found'}), 404


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        logging.info("Database tables created")
    logging.info("About to start the server on host 0.0.0.0, port %s", os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5001)), debug=True)