import json
import random
import logging

from flask import Flask
from flask import request, make_response

import models
import uuid

app = Flask(__name__, static_folder='../dist', static_path='')

if not app.debug:
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    app.logger.addHandler(stream_handler)


def elo(winner_elo, loser_elo):
    D = min(400, max(-400, winner_elo - loser_elo))
    K = 20
    p = lambda D: 1. / (1 + 10 ** (- D / 400))
    winner_elo = winner_elo + K * (1 - p(D))
    loser_elo = loser_elo + K * (0 - p(-D))
    return winner_elo, loser_elo


def update_score(winner, loser, userid, commit=True):
    if type(winner) == int and type(loser) == int:
        winner = models.Session.query(models.Images).get(winner)
        loser = models.Session.query(models.Images).get(loser)

    winner.elo, loser.elo = elo(winner.elo, loser.elo)
    if commit:  # Only add a match if we commit the changes
        match = models.Matches(user=userid, winner=winner.id, loser=loser.id)
        models.Session.add(match)

    models.Session.add_all([winner, loser])
    if commit:
        models.Session.commit()


def get_random_images():
    count = models.Session.query(models.Images).count()
    rand1, rand2 = random.randrange(0, count), random.randrange(0, count)
    img1 = models.Session.query(models.Images)[rand1]
    img2 = models.Session.query(models.Images)[rand2]
    return img1.id, img2.id

def remove(userid):
    models.Session.query(models.Matches).\
        filter(models.Matches.user==userid).delete()
    models.Session.commit()

def recalculate():
    images = models.Session.query(models.Images).all()
    images = {img.id: img for img in images}
    for img in images.values():
        img.elo = 1000
    for match in models.Session.query(models.Matches).all():
        update_score(images[match.winner], images[match.loser],
            userid=None, commit=False)
    models.Session.commit()


@app.route('/back', methods=['POST'])
def back():
    user_id = request.cookies.get('user_id')

    if not user_id:
        user = models.Users()
        models.Session.add(user)
        models.Session.commit()
    else:
        user = models.Session.query(models.Users).get(int(user_id))

    if request.method == 'POST' and request.json:
        winner = request.json.get('winner')
        loser = request.json.get('loser')
        token = request.json.get('token')
        if winner and loser:
            if token and token == user.token:
                update_score(winner, loser, user.id)
                print("lol")
            else:
                response = make_response('Error: invalid token')
                response.status_code = 403
                return response

    img1, img2 = get_random_images()
    user.token = uuid.uuid4().hex
    models.Session.add(user)
    models.Session.commit()

    payload = {'img1': img1, 'img2': img2, 'token': user.token}
    response = make_response(json.dumps(payload))
    response.set_cookie('user_id', str(user.id), max_age=3600 * 24 * 365)
    return response


@app.route('/top', methods=['GET'])
def top():
    images = models.Session.query(models.Images)\
        .order_by(models.Images.elo.desc()).limit(10)
    return json.dumps([img.id for img in images])

@app.route('/')
def index():
    return app.send_static_file('index.html')

@app.route('/top10')
def top10():
    return app.send_static_file('index.html')


if __name__ == '__main__':
    app.run()
