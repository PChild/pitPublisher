from fabric import Connection
from threading import Thread
from colorama import Fore
from types import SimpleNamespace
from string import Template
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
llm_builder.llm add_region 0,0,8,96 "1" "appear" "appear" "fastest" "12000" "left" "top"\n
llm_builder.llm add_text 0,0,8,96 "1" "8" "normal" "block" "condensed" "$color" "black" "none" "none" "--" "$pos:$team"\n
llm_builder.llm add_region 9,0,7,96 "1" "appear" "appear" "slow" "5000" "left" "middle"\n
llm_builder.llm add_text 9,0,7,96 "1" "6" "normal" "block" "condensed" "$color" "black" "none" "none" "--" "$name"\n
''')

match_sign_text = Template('''
llm_builder.llm new_msg 0,0,16,96 "normal"
llm_builder.llm add_region 0,0,8,96 "1" "appear" "appear" "fastest" "16000" "left" "middle"
llm_builder.llm add_text 0,0,8,96 "1" "8" "normal" "block" "normal" "yellow" "black" "none" "none" "--" \\""On Field:  $curr\\""
llm_builder.llm add_region 8,0,8,96 "1" "appear" "appear" "fastest" "16000" "left" "bottom"   
llm_builder.llm add_text 8,0,8,96 "1" "8" "normal" "block" "normal" "yellow" "black" "none" "none" "--" \\""Our Next:  $next\\""
''')


time_sign_text = Template('''
llm_builder.llm new_msg 0,0,16,96 "normal"
llm_builder.llm add_region 0,0,8,52 "1" "appear" "appear" "fastest" "16000" "left" "middle"
llm_builder.llm add_text 0,0,8,52 "1" "8" "normal" "block" "condensed" "yellow" "black" "none" "none" \\""Time Now:\\""
llm_builder.llm add_region 0,53,8,43 "1" "appear" "appear" "slow" "16000" "left" "bottom"
llm_builder.llm add_df 0,53,8,43 "1" "8" "normal" "block" "condensed" "yellow" "black" "none" "none" \\""time\\"" "REALTIME" "65534,65534,1" "12_HH_MM" "ALIGNR" "6"
llm_builder.llm add_region 9,0,7,56 "1" "appear" "appear" "slow" "16000" "left" "middle"
llm_builder.llm add_text 9,0,7,56 "1" "6" "normal" "block" "condensed" "yellow" "black" "none" "none" \\""Our Next:\\""
llm_builder.llm add_region 9,57,7,39 "1" "appear" "appear" "slow" "16000" "right" "middle"
llm_builder.llm add_text 9,57,7,39 "1" "6" "normal" "block" "condensed" "yellow" "black" "none" "none" \\""$matchtime\\""
''')


# Sets up colors based on sign type for both real hardware and sim
def get_color(conn):
    color = Fore.YELLOW if is_sim else 'yellow'
    if 'red' in conn.host:
        color = Fore.RED if is_sim else 'red'
    elif 'blue' in conn.host:
        color = Fore.GREEN if is_sim else 'green' 
    return color

# Helper function to run repetitive connection tasks for updating signs.
def run_2l_update(conn, file_build_str):
    conn.run("rm -f /tmp/test")
    conn.run(file_build_str)
    conn.run("localmsgs delete -f ALL")
    conn.run('localmsgs compose -e /tmp/test -f mymsg.llm')
    conn.close()

# Logic function that deals with two line sign crap.  
def update_2l_sign(conn, text):
    color = get_color(conn)
    
    if 'red' in conn.host or 'blue' in conn.host:
        team_name = '\\"' + team_names[text] + '\\"'
        team_val = '\\"' + ' ' * (7 - len(text)) + text + '\\"'
        
        if is_sim:
            print(color + "%s:%s" % (conn.host[-1], team_val) + '\n' + team_name + Fore.WHITE)
        
        else:
            file_build_str = 'echo -e "' + team_sign_text.substitute(pos=conn.host[-1], team=team_val, name=team_name, color=color) + '" >> /tmp/test'
            run_2l_update(conn, file_build_str)
            
    if 'info1' in conn.host:
        if is_sim:
            print(color + "Now Playing: " + current_match + "\nNext Match:  " + text + Fore.WHITE)
        
        else:
            file_build_str = 'echo -e "' + match_sign_text.substitute(curr=current_match, next=text) + '" >> /tmp/test'
            run_2l_update(conn, file_build_str)
    
    if 'info2' in conn.host:
        if is_sim:
            print(color + "Predicted:", text)
            print(color + "Current:", time.strftime("%I:%M"))
        
        else:
            file_build_str = 'echo -e "' + time_sign_text.substitute(matchtime=text) + '" >> /tmp/test' #TODO fix next match time
            run_2l_update(conn, file_build_str)

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
        conn = SimpleNamespace(host=conn['name']) if is_sim else conn # use sign name as connection if sim
        if conn.host != 'info1': # handle info1 separately as it updates with the field, not us.
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

# Finds the earliest match in the schedule that doesn't have a result yet.
def get_current_event_match(event):
    team_matches = sorted(tba.event_matches(event), key=lambda match: match['time'])
    next_match = team_matches[-1]
    for match in team_matches:
        if match['post_result_time'] is None:
            next_match = match
            break
    return next_match    

# Helper function to update just the next match sign in its own thread.
def update_now_playing():
    sign = settings['signs'][0]
    conn = sign if is_sim else Connection('inova@'+sign['name'], connect_kwargs={'password':sign['pass']})
    conn = SimpleNamespace(host=conn['name']) if is_sim else conn #use sign name as connection if sim
    t = Thread(target=update_sign, args=(conn, displayed_match))
    t.start()
    t.join()

# Check if the signs need to be updated by comparing match #, team #s, also logic for now playing
def check_match_status():   
    global displayed_match, red_teams, blue_teams, current_match
    next_match = get_next_match(settings['team'], settings['event'])
    new_match = next_match['comp_level'].upper() + str(next_match['match_number'])!= displayed_match
    if new_match:
        displayed_match = next_match['comp_level'].upper() + str(next_match['match_number'])
    
    new_curr = get_current_event_match(settings['event'])
    now_playing = new_curr['comp_level'].upper() + str(new_curr['match_number'])
    if now_playing != current_match:
        current_match = now_playing        
        update_now_playing()
    
    
    new_red_teams = format_team_keys(next_match['alliances']['red']['team_keys']) != red_teams
    new_blue_teams = format_team_keys(next_match['alliances']['blue']['team_keys']) != blue_teams
    
    if new_match or new_red_teams or new_blue_teams:
        red_teams = format_team_keys(next_match['alliances']['red']['team_keys'])
        blue_teams = format_team_keys(next_match['alliances']['blue']['team_keys'])
        
        
        try:
            match_time = time.strftime('%_I:%M', time.localtime(next_match['predicted_time']))
        except:
            # fuck you microsoft
             match_time = time.strftime('%#I:%M', time.localtime(next_match['predicted_time']))
        
        print('Updating screens to match', displayed_match)
        update_displays(red_teams, blue_teams, displayed_match, match_time)
        
# simple func to grab team names when the script starts
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
