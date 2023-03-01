from fabric import Connection
from threading import Thread
from colorama import Fore
from types import SimpleNamespace
from string import Template
from io import StringIO
import tbapy
import time
import json

settings = json.load( open('settings.json') )
tba = tbapy.TBA(settings['key'])
is_sim = settings['is_sim']
use_simple = settings['use_simple']

displayed_match = 'NM-1'
pred_time = '00:00'
red_teams = []
blue_teams = []
team_names = {}
current_match = 'NM-2'

team_sign_text = Template('''
llm_builder.llm new_msg 0,0,16,96 "normal"\n
llm_builder.llm add_region 0,0,8,96 "1" "appear" "appear" "fastest" "12000" "left" "middle"\n
llm_builder.llm add_text 0,0,8,96 "1" "8" "normal" "block" "normal" "$color" "black" "none" "none" "--" "$pos:$team"\n
llm_builder.llm add_region 8,0,8,96 "1" "ribbon_left" "ribbon_left" "slow" "5000" "left" "bottom"\n
llm_builder.llm add_text 8,0,8,96 "1" "8" "normal" "block" "normal" "$color" "black" "none" "none" "--" "$name"\n
''')

match_sign_text = Template('''
llm_builder.llm new_msg 0,0,16,96 "normal"
llm_builder.llm add_region 0,0,8,96 "1" "appear" "appear" "fastest" "16000" "left" "middle"
llm_builder.llm add_text 0,0,8,96 "1" "8" "normal" "block" "normal" "$color" "black" "none" "none" "--" "On Field: M$curr"
llm_builder.llm add_region 8,0,8,96 "1" "appear" "appear" "fastest" "16000" "left" "bottom"   
llm_builder.llm add_text 8,0,8,96 "1" "8" "normal" "block" "normal" "$color" "black" "none" "none" "--" "Our Next:  $next"
''')



time_sign_text = Template('''
llm_builder.llm new_msg 0,0,16,96 "normal"\n
llm_builder.llm add_region 0,0,8,96 "1" "appear" "appear" "fastest" "16000" "left" "middle"\n
llm_builder.llm add_text 0,0,8,96 "1" "8" "normal" "block" "normal" "$color" "black" "none" "none" "--" "Now Playing: $curr"
llm_builder.llm add_region 8,0,8,96 "1" "appear" "appear" "slow" "16000" "left" "bottom"   
llm_builder.llm add_text 8,0,8,96 "1" "8" "normal" "block" "normal" "$color" "black" "none" "none" "--" "Next Match:  $next"
''')


def get_color(conn):
    color = Fore.YELLOW if is_sim else 'yellow'
    if 'red' in conn.host:
        color = Fore.RED if is_sim else 'red'
    elif 'blue' in conn.host:
        color = Fore.GREEN if is_sim else 'green' 
    return color

def update_2l_sign(conn, text):
    color = get_color(conn)
    
    if 'red' in conn.host or 'blue' in conn.host:
        team_name = '\\"' + team_names[text] + '\\"'
        team_val = '\\"' + ' ' * (7 - len(text)) + text + '\\"'
        print(team_val)
        
        if is_sim:
            print(color + "%s:%s" % (conn.host[-1], team_val) + '\n' + team_name + Fore.WHITE)
        
        else:
            conn.run("rm -f /tmp/test")
            file_build_str = 'echo -e "' + team_sign_text.substitute(pos=conn.host[-1], team=team_val, name=team_name, color=color) + '" >> /tmp/test'
            conn.run(file_build_str)
            conn.run("localmsgs delete -f ALL")
            conn.run('localmsgs compose -e /tmp/test -f mymsg.llm')
            conn.close()
            
    
    if 'info1' in conn.host:
        if is_sim:
            print(color + "Now Playing: " + current_match + "\nNext Match:  " + displayed_match + Fore.WHITE)
        
        else:
            send_file = StringIO(match_sign_text.substitute(curr=current_match, next=displayed_match, color=color))
            #conn.put(send_file, remote='/tmp/test/')
            #conn.run('localmsgs compose -e /tmp/test -f mymsg.llm')
            conn.close()
    
    if 'spare1' in conn.host:
        if is_sim:
            print(color + "Scheduled: " + text +"\nPredicted: " + pred_time + Fore.WHITE)
        

# basic function to update an individual sign with specified text and color. 
def update_sign(conn, text):
    if use_simple:
        color = get_color(conn)
        text_val = str(text).upper()
        
        if is_sim:
            print(color + str(text_val) + Fore.WHITE)
        else:
            conn.run("localmsgs delete -f ALL")
            conn.run("localmsgs compose -c %s -d 0 -f test.llm -p appear -s 16 -t '%s'" % (color, text_val))
            conn.close()
    else:
        update_2l_sign(conn, str(text).upper())
    
# takes in red and blue teams, and basic match info to update all displays in parallel
def update_displays(red_teams, blue_teams, match_num, match_time):
    signs = settings['signs']
    
    connections = signs if is_sim else [Connection('inova@'+sign['name'], connect_kwargs={'password':sign['pass']}) for sign in signs]
    sign_data = [match_num] + red_teams + [match_time] + blue_teams # this concatenation means the sign list order matters
    
    threads = []
    for idx, conn in enumerate(connections):
        conn = SimpleNamespace(host=conn['name']) if is_sim else conn #use sign name as connection if sim
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

# remove leading 'FRC' from team keys, prepend _ to pad text, account for 1 to 4 digit teams with a padder
def format_team_keys(team_keys):
    fixed_list = []
    if use_simple:
        for idx, t in enumerate(team_keys[:3]):
            padder = ' ' * (7 - len(t))
            fixed_list.append('_' + str(idx + 1) + ': ' + padder + t[3:])
    else:
        for idx, t in enumerate(team_keys[:3]):
            fixed_list.append(t[3:])
    return fixed_list        

# Check if the signs need to be updated by comparing match #, team #s
def check_match_status():   
    global displayed_match, red_teams, blue_teams
    next_match = get_next_match(settings['team'], settings['event'])
    
    new_match = next_match['comp_level'].upper() + str(next_match['match_number'])!= displayed_match
    new_red_teams = format_team_keys(next_match['alliances']['red']['team_keys']) != red_teams
    new_blue_teams = format_team_keys(next_match['alliances']['blue']['team_keys']) != blue_teams
    
    if new_match or new_red_teams or new_blue_teams:
        red_teams = format_team_keys(next_match['alliances']['red']['team_keys'])
        blue_teams = format_team_keys(next_match['alliances']['blue']['team_keys'])
        displayed_match = next_match['comp_level'].upper() + str(next_match['match_number'])
        
        match_time = time.strftime('%I:%M %p', time.localtime(next_match['time']))
        
        print('Updating screens to match', displayed_match)
        update_displays(red_teams, blue_teams, displayed_match, match_time)
        

def get_team_names():
    global team_names
    for team in tba.event_teams(settings['event']):
        team_names[str(team['team_number'])] = team['nickname'][:settings['name_lim']]

# Main function to run code.  
def main():
    get_team_names()
    
    while True:
        check_match_status()
        time.sleep(settings['delay'])
        
if __name__ == "__main__":
    main()
