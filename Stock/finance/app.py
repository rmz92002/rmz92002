import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    stocks = db.execute("select stock, symbol, sum(shares) as totalshares from history where user_id = ? group by symbol having totalshares >0", session["user_id"])
    users = db.execute("SELECT * FROM users where id = ?", session.get("user_id"))
    cash = users[0]["cash"]
    holdings = []
    grand_total = 0
    for stock in stocks:
        stock_price = lookup(stock["Symbol"])
        holdings.append({
            "Symbol" : stock_price["symbol"],
            "Name" : stock["Stock"],
            "Shares" : stock["totalshares"],
            "Price": stock_price["price"],
            "Total": stock["totalshares"] * stock_price["price"]
        })
        grand_total += stock["totalshares"] * stock_price["price"]

    return render_template("index.html", cash=cash, holdings=holdings, grand_total= grand_total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        if not request.form.get("shares") or not request.form.get("symbol"):
            return apology("stock or number of shares invalid", 403)

        stock = lookup(request.form.get("symbol"))
        shares = int(request.form.get("shares"))
        row = db.execute("select * from users where id = ?", session.get("user_id"))
        cash = row[0]["cash"]
        updated_cash = cash - (stock["price"] * shares)

        if float(request.form.get("shares")) < 0:
            return apology("typed nagative number", 403)

        if updated_cash < 0:
            return apology("not enough cash bitch", 403)

        if lookup(request.form.get("symbol")) == None:
            return redirect("/buy")

        db.execute("UPDATE users SET cash = ? WHERE id= ?", row[0]["cash"]-(float(request.form.get("shares"))* stock["price"]), session.get("user_id"))
        db.execute("INSERT INTO history (user_id, Symbol, Stock, Shares, Price, Total, type) VALUES(?, ?, ?, ?, ?, ?, ?)", session.get("user_id"), request.form.get("symbol"), stock["name"], request.form.get("shares"), stock["price"], (float(request.form.get("shares"))* stock["price"]), "Bought")
        #seeing if user already bought the stock
        return apology("success", 403)

    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    stocks = db.execute("select stock, symbol, price, type, total, ABS(shares) as totalshares from history where user_id = ?", session["user_id"])
    return render_template("history.html", stocks=stocks)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        if lookup(request.form.get("symbol")) == None:
            return redirect("/quote")
        else:
            symbol = lookup(request.form.get("symbol"))
            return render_template("quoted.html", symbol=symbol)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":

        #if user does not provide username or password
        if not request.form.get("username") or not request.form.get("password"):
            return apology("invalid username/password", 403)
        #check if password match
        elif request.form.get("password") != request.form.get("password2"):
            return apology("Password does not match", 403)

        #check if username exists in the database
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))
        if len(rows) == 1:
            return apology("username taken", 403)

        #integrate the password and username into the database
        db.execute("Insert into users (username, hash) Values (?,?)", request.form.get("username"), generate_password_hash(request.form.get("password")))
        return redirect("/login")
    else:
        return render_template("register.html")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":
        if not request.form.get("shares") or not request.form.get("symbol"):
            return apology("stock or number of shares invalid", 403)

        stock = lookup(request.form.get("symbol"))
        shares = int(request.form.get("shares"))

        row = db.execute("select * from users where id = ?", session.get("user_id"))
        stocks = db.execute("select stock, symbol, sum(shares) as totalshares from history where user_id = ? and symbol = ? group by symbol having totalshares >0", session["user_id"], request.form.get("symbol"))
        cash = row[0]["cash"]
        updated_cash = cash + (stock["price"] * shares)


        if float(request.form.get("shares")) < 0:
            return apology("typed nagative number", 403)

        if lookup(request.form.get("symbol")) == None:
            return redirect("/sell")

        #see if the shares exists

        if stocks[0]["totalshares"]< shares:
            return apology("not enough shares", 403)


        db.execute("UPDATE users SET cash = ? WHERE id= ?", row[0]["cash"]+(float(request.form.get("shares"))* stock["price"]), session.get("user_id"))
        db.execute("INSERT INTO history (user_id, Symbol, Stock, Shares, Price, Total, type) VALUES(?, ?, ?, ?, ?, ?, ?)", session.get("user_id"), request.form.get("symbol"), stock["name"], int(-1)* shares, stock["price"], (float(request.form.get("shares"))* stock["price"]), "Sold")
        #seeing if user already bought the stock
        return apology("success", 403)

    else:
        stocks  = db.execute("select Symbol, sum(shares) as totalshares from history where user_id = ? group by symbol having totalshares >0", session["user_id"])
        return render_template("sell.html", symbols=[stock["Symbol"] for stock in stocks])
