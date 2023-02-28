from fabric import Connection
from threading import Thread
from colorama import Fore
import tbapy
import time
import json

settings = json.load( open('settings.json') )
is_sim = settings['is_sim']
signs = settings['signs']

tba = tbapy.TBA(settings['key'])

displayed_match = ''
red_teams = []
blue_teams = []

# basic function to update an individual sign with specified text and color. 
def update_sign(conn, text):
    # use the hostname to choose color to apply.
    color = 'yellow'
    if 'red' in conn.host:
        color = 'red'
    elif 'blue' in conn.host:
        color = 'green'
        
    conn.run("localmsgs delete -f ALL")
    conn.run("localmsgs compose -c %s -d 0 -f test.llm -p appear -s 16 -t '%s'" % (color, str(text).upper()))
    conn.close()

# simulate sign updates in the terminal instead of on real hardware. 
# Colors, spacing 
# should match. Sign ordering is nondeterministic, I think.
def sim_update_sign(conn, text):
    color = Fore.YELLOW
    if 'red' in conn:
        color = Fore.RED
    elif 'blue' in conn:
        color = Fore.GREEN
        
    print(color + str(text) + Fore.WHITE)
    
# initialize displays to show their role
def init_signs():
    if is_sim:
        connections = signs
    else:
        connections = [Connection('inova@'+sign['name'], connect_kwargs={'password':sign['pass']}) for sign in signs]

    threads = []
    for conn in connections:
        if is_sim:
            t = Thread(target=sim_update_sign, args=(conn['name'], conn['name']))
        else:
            t = Thread(target=update_sign, args=(conn, conn.host))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

# takes in red and blue teams, and basic match info to update all displays in parallel
def update_displays(red_teams, blue_teams, match_num, match_time):
    if is_sim:
        connections = signs
    else:
        connections = [Connection('inova@'+sign['name'], connect_kwargs={'password':sign['pass']}) for sign in signs]
    sign_data = [match_num] + red_teams + [match_time] + blue_teams # this concatenation means the sign list order matters
    
    threads = []
    for idx, conn in enumerate(connections):
        if is_sim:
            t = Thread(target=sim_update_sign, args=(conn['name'], sign_data[idx]))
        else:
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
        if match['post_result_time'] is None:
            next_match = match
            break
    return next_match

# remove leading 'FRC' from team keys, prepend _ to pad text, account for 3 and 4 digit teams with a padder
def format_team_keys(team_keys):
    fixed_list = []
    for idx, t in enumerate(team_keys):
        padder = ' ' * (7 - len(t))
        fixed_list.append('_' + str(idx + 1) + ': ' + padder + t[3:])
    
    return fixed_list        

# Check if the signs need to be updated
def check_match_status():   
    global displayed_match, red_teams, blue_teams
    next_match = get_next_match(settings['team'], settings['event'])
    
    new_match = next_match['match_number'] != displayed_match
    new_red_teams = format_team_keys(next_match['alliances']['red']['team_keys']) != red_teams
    new_blue_teams = format_team_keys(next_match['alliances']['blue']['team_keys']) != blue_teams
    
    if new_match or new_red_teams or new_blue_teams:
        red_teams = format_team_keys(next_match['alliances']['red']['team_keys'])
        blue_teams = format_team_keys(next_match['alliances']['blue']['team_keys'])
        
        match_time = time.strftime('%I:%M %p', time.localtime(next_match['time']))
        update_displays(red_teams, blue_teams, next_match['comp_level'].upper() + str(next_match['match_number']), match_time)
        
        # store that we updated the match so we don't need perform an update for this match again.
        displayed_match = next_match['match_number']
        
# Main function to run code.  
def main():
    # init_signs()

    while True:
        check_match_status()
        time.sleep(settings['delay'])
        
if __name__ == "__main__":
    main()