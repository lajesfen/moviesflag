from flask import Flask, render_template, request, jsonify
import requests
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)
apikey = "9ad2644b"

cache = {
    "movieSearch": {},
    "movieDetails": {},
    "countryFlags": {}
}

def searchfilms(search_text):
    if search_text in cache["movieSearch"]:
        print("Found search results for", search_text, "in cache")
        return cache["movieSearch"][search_text]

    url = f"https://www.omdbapi.com/?s={search_text}&apikey={apikey}"
    response = requests.get(url)
    if response.status_code == 200:
        results = response.json()
        cache["movieSearch"][search_text] = results
        print("Calling Search API")
        return results
    else:
        print("Failed to retrieve search results.")
        return None

def getmoviedetails(imdb_id):
    if imdb_id in cache["movieDetails"]:
        print("Found movie details for", imdb_id, "in cache")
        return cache["movieDetails"][imdb_id]

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
        cache["movieDetails"][imdb_id] = entry
        print("Calling Movie API for", imdb_id)
        return entry
    else:
        print("Failed to retrieve movie details.")
        return None

def get_country_flag(country_name):
    if country_name in cache["countryFlags"]:
        print("Found flag for", country_name, "in cache")
        return cache["countryFlags"][country_name]

    url = f"https://restcountries.com/v3.1/name/{country_name}?fullText=true"
    response = requests.get(url)
    if response.status_code == 200:
        country_data = response.json()
        if country_data:
            flag_url = country_data[0].get("flags", {}).get("svg", None)
            cache["countryFlags"][country_name] = flag_url
            print("Calling Flag API for", country_name)
            return flag_url
    print("Failed to retrieve flag for country:", country_name)
    return None

def merge_data_with_flags(filter, page, page_limit):
    film_search = searchfilms(filter)

    start_index = (page - 1) * page_limit
    end_index = start_index + page_limit
    paginated_movies = film_search['Search'][start_index:end_index]

    movies_details_with_flags = []
    with ThreadPoolExecutor() as executor:
        movies_details = list(executor.map(lambda movie: getmoviedetails(movie["imdbID"]), paginated_movies))
        
        for movie in movies_details:
            country_names = movie["Country"].split(", ")
            countries = [{"name": name, "flag": get_country_flag(name)} for name in country_names]
            movies_details_with_flags.append({
                "title": movie["Title"],
                "year": movie["Year"],
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
    return jsonify(cache)

if __name__ == "__main__":
    app.run(debug=True)
