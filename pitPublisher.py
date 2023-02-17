from fabric import Connection
from threading import Thread
import tbapy
import time
import json

settings = json.load( open('settings.json') )
tba = tbapy.TBA(settings['key'])

# ordering should be red, blue, match #, match time because of enumeration in update_displays()
# todo: assign hostnames based on roles for all signs. This makes this code noop currently.
signs = settings['signs']

displayed_match = None

# basic function to update an individual sign with specified text and color. 
def update_sign(conn, text):
    # use the hostname to choose color to apply.
    color = 'yellow'
    if 'red' in conn.host:
        color = 'red'
    elif 'blue' in conn.host:
        color = 'green'
        
    conn.run("localmsgs delete -f ALL")
    conn.run("localmsgs compose -c %s -d 0 -f test.llm -p appear -s 11 -t '%s'" % (color, text.upper()), hide=True)
    conn.close()
    
# initialize displays to show their role
def init_signs():
    connections = [Connection('inova@'+sign['name'], connect_kwargs={'password':sign['pass']}) for sign in signs]

    threads = []
    for conn in connections:
        t = Thread(target=update_sign, args=(conn, conn.host))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

# takes in red and blue teams, and basic match info to update all displays in parallel
def update_displays(red_teams, blue_teams, match_num, match_time):
    connections = [Connection('inova@'+sign['name'], connect_kwargs={'password':sign['pass']}) for sign in signs]
    sign_data = red_teams + blue_teams + [match_num] + [match_time] # this concatenation means the sign list order matters
    
    threads = []
    for idx, conn in enumerate(connections):
        t = Thread(target=update_sign, args=(conn, sign_data[idx]))
        threads.append(t)
        t.start()
    
    for t in threads:
        t.join()

# Find the earliest scheduled match that does not have a posted result.
def get_next_match(team, event):
    team_matches = sorted(tba.team_matches(team, event), key=lambda match: match['time'])
    next_match = team_matches[-1]
    for match in team_matches:
        if match['post_result_time'] < 100000: # todo: check behaviour of this on real TBA feed.
            next_match = match
            break
    return next_match

# remove leading 'FRC' from team keys, prepend _ to pad text, account for 3 and 4 digit teams with a padder
def format_team_keys(team_keys):
    fixed_list = []
    for idx, t in team_keys:
        padder = ' ' if len(t) > 6 else ''
        fixed_list.append('_' + str(idx + 1) + ': ' + padder + t[3:])
    
    return fixed_list        

# Check if the signs need to be updated
def check_match_status():   
    next_match = get_next_match(settings['team'], settings['event'])        
    
    if next_match['match_number'] != displayed_match:
        red_teams = format_team_keys(next_match['alliances']['red']['team_keys'])
        blue_teams = format_team_keys(next_match['alliances']['blue']['team_keys'])
        update_displays(red_teams, blue_teams, next_match['match_number'], 0) # todo: fetch actual time from matches
        
        # store that we updated the match so we don't need perform an update for this match again.
        displayed_match = next_match['match_number']
        
        
def main():
    init_signs()
    
    while True:
        check_match_status()
        time.sleep(settings['delay'])