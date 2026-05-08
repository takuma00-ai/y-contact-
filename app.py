from flask import Flask, render_template, request, redirect,session,flash,jsonify
import sqlite3,os
from werkzeug.utils import secure_filename


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(BASE_DIR, "user.db")

conn = sqlite3.connect(db_path)


app=Flask(__name__)
app.secret_key="secret_key"
app.secret_key="secret"

#DB接続
def get_db():
    return sqlite3.connect(db_path)

def init_db():
    db=get_db()

    #db.execute("ALTER TABLE messages ADD COLUMN image_path TEXT")

    #ログインテーブル users
    db.execute("""
               CREATE TABLE IF NOT EXISTS users (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               username TEXT,
               password TEXT
               )
               """)
    #イベントテーブル eventa
    db.execute("""
               CREATE TABLE IF NOT EXISTS events(
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               title TEXT,
               content TEXT,
               date TEXT,
               author_id INTEGER
               )
               """)
    #イベント参加テーブル event_join
    db.execute("""
               CREATE TABLE IF NOT EXISTS event_join(
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               user_id INTEGER,
               event_id INTEGER,
               status INTEGER
               )
               """)
    #既読・未既読取得のテーブル
    db.execute("""
               CREATE TABLE IF NOT EXISTS message_reads (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               message_id INTEGER,
               username TEXT,
               UNIQUE(message_id,username)
               )
            """)
    #チャットbox（messages)てーぶる
    db.execute("""
              CREATE TABLE IF NOT EXISTS messages (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id INTEGER,
              event_id INTEGER,
              content TEXT,
              created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
              image_path TEXT
              )
              """)
    
    db.commit()
    db.close()
#アカウント新規作成画面
@app.route("/register",methods=["POST"])
def create_account():
    username=request.form["username"]
    password=request.form['password']

    conn=get_db()
    c=conn.cursor()

    c.execute("SELECT * FROM users WHERE username=?",(username,))
    existing=c.fetchone()

    print("username:",username)
    print("existing:",existing)

    if existing:
        flash("このユーザー名は使われています") 
        return redirect("/create_new_user")
    
    #登録
    c.execute("INSERT INTO users (username,password) VALUES (?,?)",(username,password))
    conn.commit()
    conn.close()
    flash("ユーザー登録完了！ログインしてください")
    return redirect("/")


@app.route("/create_new_user",methods=["GET"])
def create_new_user():
    return render_template("create_new_user.html")


#ログイン画面
@app.route("/",methods=["GET","POST"])
def login():
    if request.method=="POST":
        username=request.form["username"]
        password=request.form["password"]

        db=get_db()
        user=db.execute(
            "SELECT * FROM users WHERE username=? AND password=?",
            (username,password)
            ).fetchone()
        db.close()

        if user:
            session["user"]=username
            session["user_id"]=user[0]
            return redirect("/home")
        else:
            return"ログイン失敗"
    return render_template("login.html")

#ホーム画面
@app.route("/home")
def home():

    conn=get_db()
    c=conn.cursor()

    user=session["user"]
    c.execute("""
        SELECT COUNT(*)
        FROM messages
        WHERE id NOT IN(
              SELECT message_id
              FROM message_reads
              WHERE username = ?
        )
    """,(user,))

    unread_count=c.fetchone()[0]

    if "user" in session:
        return render_template("home.html",user=session["user"],unread_count=unread_count)
    return redirect("/") 
#ユーザー登録
@app.route("/create_test_user")
def register():
    db=get_db()
    db.execute("INSERT INTO users (username,password) VALUES (?, ?)",("test","1234"))
    db.commit()
    db.close()
    return "ユーザー登録完了! (test / 1234)"

#イベントページ
@app.route("/events")
def events():
    conn=get_db()
    c=conn.cursor()

    user=session["user"]
    c.execute("""
        SELECT COUNT(*)
        FROM messages
        WHERE id NOT IN(
              SELECT message_id
              FROM message_reads
              WHERE username=?
              )
    """,(user,))
    unread_count=c.fetchone()[0]

    events=conn.execute("""
        SELECT 
            events.*,
            users.username,
            COUNT(event_join.id) as join_count
        FROM events
        JOIN users ON events.author_id = users.id
        LEFT JOIN event_join ON events.id = event_join.event_id
        GROUP BY events.id
        ORDER BY date
        """).fetchall()
    
    joined_map={}

    if "user_id" in session:
        user_id=session["user_id"]

        joined_events=conn.execute("""
            SELECT event_id FROM event_join
            WHERE user_id=?
        """,(user_id,)).fetchall()
        #{event_id:True}のかたちにする
        joined_map={row[0]:True for row in joined_events}

    conn.close()
    #eventsページのpythonに渡す
    return render_template(
        "events.html", 
        events=events,
        joined_map=joined_map,
        unread_count=unread_count)

#イベント投稿ページ
@app.route("/create_event",methods=["GET","POST"])
def create_event():
    if "user" not in session:
        return redirect("/")
    if request.method=="POST":
        title=request.form["title"]
        content=request.form["content"]
        date=request.form["date"]
        author_id=session["user_id"]

        db=get_db()
        db.execute(
            "INSERT INTO events (title,content,date,author_id) VALUES (?,?,?,?)",
            (title,content,date,author_id)
        )
        db.commit()
        db.close()
        return redirect("/events")
    return render_template("create_events.html")
#イベント編集ページ
@app.route("/edit_event/<int:event_id>",methods=["GET","POST"])
def edit_event(event_id):
    db=get_db()
    if request.method=="POST":
        title=request.form['title']
        content=request.form['content']
        date=request.form['date']

        db.execute(
            "UPDATE events SET title=?, content=?, date=? WHERE id=?",
            (title,content,date,event_id)
        )
        db.commit()
        db.close()
        return redirect("/events")
    #GETのときの処理（最初にページ開くとき＝GET）
    event=db.execute(
        "SELECT * FROM events WHERE id=?", 
        (event_id,)
    ).fetchone()
    db.close()
    return render_template("edit_event.html", event=event)
#イベント参加ボタン
@app.route("/join/<int:event_id>")
def join(event_id):
    user_id=session["user_id"]
    db=get_db()
    #解説/joinedの定義user_id,event_id
    joined=db.execute(
        "SELECT * FROM event_join WHERE user_id=? AND event_id=?",
        (session["user_id"],event_id)
    ).fetchone()
    #もしjoinedにでーたがなかったら
    if not joined:
        db.execute(
            "INSERT INTO event_join (user_id,event_id,status) VALUES (?,?,?)",
            (user_id,event_id,"join")
        )
        db.commit()
    db.close()
    return redirect("/events")
#イベントの参加取り消しボタン
@app.route("/cancel/<int:event_id>")
def cancel(event_id):
    user_id=session["user_id"]

    db=get_db()
    db.execute(
        "DELETE FROM event_join WHERE user_id=? AND event_id=?",
        (user_id,event_id)
    )
    db.commit()
    db.close()
    return redirect("/events")

#チャット機能
#全体チャット
@app.route("/chat")
def global_chat():
    #conn=sqlite3.connect("user.db")
    conn=get_db()
    c=conn.cursor()

    c.execute("""
        SELECT messages.id,messages.content,users.username,messages.created_at,messages.image_path
        FROM messages
        JOIN users ON messages.user_id=users.id
        WHERE event_id IS NULL
        ORDER BY messages.created_at ASC
    """)

    messages=c.fetchall()

    for msg in messages:
        print(msg)

    #既読確認処理コード
    user=session.get("user")

    for msg in messages:
        #チャット開いての既読確認
        c.execute("""
                INSERT OR IGNORE INTO message_reads (message_id,username)
                  VALUES (?,?)
                  """,(msg[0],user))

    conn.commit()
        
    #既読人数の取得
    c.execute("""
            SELECT message_id,COUNT(*)-1 as read_count
            FROM message_reads
            GROUP BY message_id
        """)
    read_date=c.fetchall()
    read_counts={row[0]:row[1] for row in read_date}
        

    c.execute("SELECT id, title FROM events")
    events=c.fetchall()


    #event_id,未読件数が入る辞書
    event_unreads={}

    c.execute("SELECT id,title FROM events")
    events=c.fetchall()

    for ev in events:
        event_id=ev[0]

        c.execute("""
            SELECT COUNT(*)
            FROM messages
            WHERE event_id =?
            AND id NOT IN(
                  SELECT message_id
                  FROM message_reads
                  WHERE username=?
            )
        """,(event_id,session["user"]))

        count=c.fetchone()[0]
        event_unreads[event_id]=count

    total_event_unreads=sum(event_unreads.values())

    conn.close()
    return render_template(
        "chat.html",
        messages=messages,
        event_id=None,
        events=events,
        read_counts=read_counts,
        event_unreads=event_unreads,
        total_event_unreads=total_event_unreads)
#イベントチャット画面表示
@app.route("/chat/<int:event_id>")
def chat(event_id):
    #conn=sqlite3.connect("user.db")
    conn=get_db()
    c=conn.cursor()
    
    #message
    c.execute("""
        SELECT messages.id, messages.content,users.username,messages.created_at,messages.image_path
        FROM messages
        JOIN users ON messages.user_id=users.id
        WHERE event_id=?
        ORDER BY messages.created_at ASC
    """,(event_id,))

    messages=c.fetchall()


    #既読確認処理コード
    user=session.get("user")

    for msg in messages:
        #チャット開いての既読確認
        c.execute("""
                INSERT OR IGNORE INTO message_reads (message_id,username)
                  VALUES (?,?)
                  """,(msg[0],user))

    conn.commit()
    
    #既読人数の取得
    c.execute("""
            SELECT message_id,COUNT(*) as read_count
            FROM message_reads
            GROUP BY message_id
        """)
    read_date=c.fetchall()
    read_counts={row[0]:row[1] for row in read_date}

    #event_id,未読件数が入る辞書
    event_unreads={}

    c.execute("SELECT id,title FROM events")
    events=c.fetchall()

    for ev in events:
        ev_id=ev[0]

        c.execute("""
            SELECT COUNT(*)
            FROM messages
            WHERE event_id =?
            AND id NOT IN(
                  SELECT message_id
                  FROM message_reads
                  WHERE username=?
            )
        """,(ev_id,session["user"]))

        count=c.fetchone()[0]
        event_unreads[ev_id]=count
    

    total_event_unreads=sum(event_unreads.values())


    #event title
    c.execute("SELECT title FROM events WHERE id = ?",(event_id,))
    event=c.fetchone()
    conn.close()
    return render_template(
        "chat.html",
        messages=messages,
        event_id=event_id,event_title=event[0],
        read_counts=read_counts,
        event_unreads=event_unreads,
        total_event_unreads=total_event_unreads)


UPLOAD_FOLDER="static/uploads"

#メッセージの送信
@app.route("/send_message",methods=["POST"])
def send_message():
    if "user_id" not in session:
        return redirect("/login")
    
    content=request.form["content"]
    event_id=request.form.get("event_id")
    user_id=session['user_id']

    if event_id =="None" or event_id =="":
        event_id=None

    #画像送信処理
    image=request.files.get("image")
    image_path=None

    if image and image.filename != "":
        filename=secure_filename (image.filename)

        os.makedirs(UPLOAD_FOLDER,exist_ok=True)

        path=os.path.join(UPLOAD_FOLDER,filename)
        image.save(path)
        image_path=f"uploads/{filename}"


    conn=get_db()
    c=conn.cursor()

    c.execute("""
        INSERT INTO messages (user_id,event_id,content,image_path)
        VALUES(?,?,?,?)
    """,(user_id,event_id,content,image_path))

    conn.commit()
    conn.close()

    if event_id:
        return redirect(f"/chat/{event_id}")
    else:
        return redirect("/chat")

#ログアウト機能
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

#通知（３秒毎の更新）
@app.route("/api/unread_counts")
def unread_connts():
    conn=get_db()
    c=conn.cursor()

    user=session["user"]
    #全体チャットの未読
    c.execute("""
        SELECT COUNT(*)
        FROM messages
        WHERE event_id IS NULL
        AND id NOT IN(
              SELECT message_id
              FROM message_reads
              WHERE username=?
              )
              """,(user,))
    global_unread=c.fetchone()[0]

    #イベントチャットの未読
    c.execute("SELECT id,title FROM events")
    events=c.fetchall()

    event_unreads={}

    for ev in events:
        ev_id=ev[0]

        c.execute("""
            SELECT COUNT(*)
            FROM messages
            WHERE event_id=?
            AND id NOT IN(
                  SELECT message_id
                  FROM message_reads
                  WHERE username=?
                  )
        """,(ev_id,user))

        count=c.fetchone()[0]

        event_unreads[ev_id] = count

        total_event_unreads=sum(event_unreads.values())

        conn.close()
        return jsonify({
            "global_unread":global_unread,
            "event_unreads":event_unreads,
            "total_event_unreads":total_event_unreads
        })

#データ消去こーど(イベント・チャット・登録アカウント) /reset_allにアクセス
@app.route("/reset_all")
def reset_all():
    conn = get_db()
    c = conn.cursor()

    c.execute("DELETE FROM message_reads")
    c.execute("DELETE FROM messages")
    c.execute("DELETE FROM users")

    c.execute("DELETE FROM sqlite_sequence WHERE name='users'")
    c.execute("DELETE FROM sqlite_sequence WHERE name='messages'")

    conn.commit()
    conn.close()

    return "全データ削除完了"

if __name__=="__main__":
    init_db()
    app.run(debug=True)

    conn=sqlite3.connect("user.db")
    db=conn.cursor()
    #ページ開くたびに既読が増えてしまうmessage_readsの削除に使用/作り直し済み
    #db.execute("DROP TABLE IF EXISTS message_reads")
