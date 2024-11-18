from flask import Flask, render_template, request, jsonify
import requests
from concurrent.futures import ThreadPoolExecutor
import sqlite3

app = Flask(__name__)
apikey = "9ad2644b"

conn = sqlite3.connect("cache.db", check_same_thread=False)
conn.row_factory = sqlite3.Row

def create_cache_tables():
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS movie (imdbID TEXT PRIMARY KEY, Title TEXT, Year REAL, Country TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS country (countryName TEXT PRIMARY KEY, flagURL TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS moviecountry (imdbID TEXT, countryName TEXT, FOREIGN KEY(imdbID) REFERENCES movie(imdbID), FOREIGN KEY(countryName) REFERENCES country(countryName))''')
    conn.commit()

def search_films(search_text):
    url = f"https://www.omdbapi.com/?s={search_text}&apikey={apikey}"
    response = requests.get(url)
    if response.status_code == 200:
        results = response.json()
        print("Calling Search API")
        return results
    else:
        print("Failed to retrieve search results.")
        return None

def get_movie_details(imdb_id):
    cursor = conn.cursor()
    cache = cursor.execute("SELECT * FROM movie WHERE imdbID=?", (imdb_id,))
    cache_res = cache.fetchone()

    if cache_res:
        print("Found movie details for", imdb_id, "in cache")
        return cache_res

    url = f"https://www.omdbapi.com/?i={imdb_id}&apikey={apikey}"
    response = requests.get(url)
    if response.status_code == 200:
        result = response.json()
        entry = {
            "imdbID": result["imdbID"],
            "Title": result["Title"],
            "Year": result["Year"],
            "Country": result["Country"]
        }
        cursor.execute("INSERT INTO movie VALUES (?, ?, ?, ?)", (entry["imdbID"], entry["Title"], entry["Year"], entry["Country"]))
        
        countries = entry["Country"].split(", ")
        for country in countries:
            cursor.execute("INSERT INTO moviecountry VALUES (?, ?)", (entry["imdbID"], country))
        
        conn.commit()
        print("Calling Movie API for", imdb_id)
        return entry
    else:
        print("Failed to retrieve movie details.")
        return None

def get_country_flag(country_name):
    cursor = conn.cursor()
    cache = cursor.execute("SELECT * FROM country WHERE countryName=?", (country_name,))
    cache_res = cache.fetchone()

    if cache_res:
        print("Found flag for", country_name, "in cache")
        return cache_res["flagURL"]

    url = f"https://restcountries.com/v3.1/name/{country_name}?fullText=true"
    response = requests.get(url)
    if response.status_code == 200:
        country_data = response.json()
        if country_data:
            flag_url = country_data[0].get("flags", {}).get("svg", None)
            cursor.execute("INSERT INTO country VALUES (?, ?)", (country_name, flag_url))
            conn.commit()
            print("Calling Flag API for", country_name)
            return flag_url
    print("Failed to retrieve flag for country:", country_name)
    return None

def merge_data_with_flags(filter, page, page_limit):
    film_search = search_films(filter)

    start_index = (page - 1) * page_limit
    end_index = start_index + page_limit
    paginated_movies = film_search['Search'][start_index:end_index]

    movies_details_with_flags = []
    cursor = conn.cursor()
    for movie in paginated_movies:
            movie_details = get_movie_details(movie["imdbID"])

            if movie_details:
                query = cursor.execute("SELECT countryName FROM moviecountry WHERE imdbID=?", (movie_details["imdbID"],))
                country_names = [row["countryName"] for row in query.fetchall()]
                countries = [{"name": name, "flag": get_country_flag(name)} for name in country_names]
                movies_details_with_flags.append({
                    "title": movie_details["Title"],
                    "year": movie_details["Year"],
                    "countries": countries
                })

    return movies_details_with_flags

@app.route("/")
def index():
    filter = request.args.get("filter", "").upper()
    page = int(request.args.get("page", 1))
    page_limit = int(request.args.get("page_limit", 5))
    movies = merge_data_with_flags(filter, page, page_limit)
    return render_template("index.html", movies=movies)

@app.route("/api/movies")
def api_movies():
    filter = request.args.get("filter", "").upper()
    page = int(request.args.get("page", 1))
    page_limit = int(request.args.get("page_limit", 5))
    return jsonify(merge_data_with_flags(filter, page, page_limit))

@app.route("/cache")
def cache_data():
    cursor = conn.cursor()
    cache = {
        "movies": cursor.execute("SELECT * FROM movie").fetchall(),
        "countries": cursor.execute("SELECT * FROM country").fetchall(),
        "moviecountries": cursor.execute("SELECT * FROM moviecountry").fetchall()
    }
    return jsonify(cache)

if __name__ == "__main__":
    create_cache_tables()
    app.run(debug=True)
