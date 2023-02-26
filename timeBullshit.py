import time
import tbapy
import time
import json

settings = json.load( open('settings.json') )
tba = tbapy.TBA(settings['key'])

team_matches = sorted(tba.team_matches(settings['team'], settings['event']), key=lambda match: match['time'])
next_match = team_matches[-1]


my_time = time.strftime('%a %#I:%M %p', time.localtime(next_match['time']))

print(my_time)