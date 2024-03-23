from fabric import Connection
from threading import Thread
from colorama import Fore
from types import SimpleNamespace
from string import Template
import keyboard
import tbapy
import time
import json

settings = json.load(open('settings.json'))
tba = tbapy.TBA(settings['key'])
is_sim = settings['is_sim']
use_simple = settings['use_simple']
offline = settings['offline']
event = settings['event']
team = settings['team']

displayed_match = 'NM-1'
pred_time = '00:00'
red_teams = []
blue_teams = []
team_names = {'0': ''}
current_match = 'NM-2'
match_idx = 0

team_sign_text = Template('''
llm_builder.llm new_msg 0,0,16,96 "normal"\n
llm_builder.llm add_region 0,0,8,96 "1" "appear" "appear" "fastest" "12000" "left" "top"\n
llm_builder.llm add_text 0,0,8,96 "1" "8" "normal" "block" "condensed" "$color" "black" "none" "none" "--" "$pos:$team"\n
llm_builder.llm add_region 9,0,7,96 "1" "appear" "appear" "slow" "5000" "left" "middle"\n
llm_builder.llm add_text 9,0,7,96 "1" "6" "normal" "block" "condensed" "$color" "black" "none" "none" "--" "$name"\n
''')

match_sign_text = Template('''
llm_builder.llm new_msg 0,0,16,96 "normal"
llm_builder.llm add_region 0,0,8,64 "1" "appear" "appear" "fastest" "16000" "left" "bottom"   
llm_builder.llm add_text 0,0,8,64 "1" "8" "normal" "block" "condensed" "yellow" "black" "none" "none" "--" \\""$lead\\""
llm_builder.llm add_region 0,65,8,31 "1" "appear" "appear" "fastest" "16000" "left" "bottom"   
llm_builder.llm add_text 0,65,8,31 "1" "8" "normal" "block" "condensed" "yellow" "black" "none" "none" "--" \\""$curr\\""
llm_builder.llm add_region 9,0,7,64 "1" "appear" "appear" "fastest" "16000" "left" "middle"
llm_builder.llm add_text 9,0,7,64 "1" "6" "normal" "block" "normal" "yellow" "black" "none" "none" "--" \\""Our Next:\\""
llm_builder.llm add_region 9,65,7,31 "1" "appear" "appear" "fastest" "16000" "left" "middle"
llm_builder.llm add_text 9,65,7,31 "1" "6" "normal" "block" "normal" "yellow" "black" "none" "none" "--" \\""$next\\""
''')

time_sign_text = Template('''
llm_builder.llm new_msg 0,0,16,96 "normal"
llm_builder.llm add_region 0,0,8,52 "1" "appear" "appear" "fastest" "16000" "left" "middle"
llm_builder.llm add_text 0,0,8,52 "1" "8" "normal" "block" "condensed" "yellow" "black" "none" "none" \\""Time Now:\\""
llm_builder.llm add_region 0,53,8,43 "1" "appear" "appear" "slow" "16000" "left" "bottom"
llm_builder.llm add_df 0,53,8,43 "1" "8" "normal" "block" "condensed" "yellow" "black" "none" "none" \\""time\\"" "REALTIME" "65534,65534,1" "12_HH_MM" "ALIGNR" "6"
llm_builder.llm add_region 9,0,7,56 "1" "appear" "appear" "slow" "16000" "left" "middle"
llm_builder.llm add_text 9,0,7,56 "1" "6" "normal" "block" "condensed" "yellow" "black" "none" "none" \\""$lead\\""
llm_builder.llm add_region 9,57,7,39 "1" "appear" "appear" "slow" "16000" "right" "middle"
llm_builder.llm add_text 9,57,7,39 "1" "6" "normal" "block" "condensed" "yellow" "black" "none" "none" \\""$matchtime\\""
''')


def get_color(conn):
    color = Fore.YELLOW if is_sim else 'yellow'
    if 'red' in conn.host:
        color = Fore.RED if is_sim else 'red'
    elif 'blue' in conn.host:
        color = Fore.GREEN if is_sim else 'green'
    return color


def run_2l_update(conn, file_build_str):
    conn.run("rm -f /tmp/test")
    conn.run(file_build_str)
    conn.run("localmsgs delete -f ALL")
    conn.run('localmsgs compose -e /tmp/test -f mymsg.llm')
    conn.close()


def update_2l_sign(conn, text):
    color = get_color(conn)

    if 'red' in conn.host or 'blue' in conn.host:
        team_name = team_names[text]
        team_val = ' ' * (7 - len(text)) + text

        if is_sim:
            print(color + "%s:%s" %
                  (conn.host[-1], team_val) + '\n' + team_name + Fore.WHITE)

        else:
            team_name = '\\"' + team_name + '\\"'
            team_val = '\\"' + team_val + '\\"'

            file_build_str = 'echo -e "' + team_sign_text.substitute(
                pos=conn.host[-1], team=team_val, name=team_name, color=color) + '" >> /tmp/test'
            run_2l_update(conn, file_build_str)

    if 'info1' in conn.host:
        leader = "Mode: " if offline else "On Field:"
        on_field = "Offline" if offline else current_match
        if is_sim:
            print(color + leader + on_field +
                  "\nNext Match:  " + text + Fore.WHITE)

        else:
            file_build_str = 'echo -e "' + \
                match_sign_text.substitute(lead=leader,
                                           curr=on_field, next=text) + '" >> /tmp/test'
            run_2l_update(conn, file_build_str)

    if 'info2' in conn.host:
        leader = "Our Next"
        if is_sim:
            print(color + leader, text)
            print(color + "Current:", time.strftime("%I:%M"))

        else:
            file_build_str = 'echo -e "' + \
                time_sign_text.substitute(lead=leader,
                                          matchtime=text) + '" >> /tmp/test'  # TODO fix next match time
            run_2l_update(conn, file_build_str)


def update_sign(conn, text):
    if use_simple:
        color = get_color(conn)
        text_val = str(text).upper()

        if is_sim:
            print(color + str(text_val) + Fore.WHITE)
        else:
            conn.run("localmsgs delete -f ALL")
            conn.run(
                "localmsgs compose -c %s -d 0 -f test.llm -p appear -s 16 -t '%s'" % (color, text_val))
            conn.close()
    else:
        update_2l_sign(conn, str(text).upper())


def update_displays(red_teams, blue_teams, match_num, match_time):
    signs = settings['signs']

    connections = signs if is_sim else [Connection(
        'inova@'+sign['name'], connect_kwargs={'password': sign['pass']}) for sign in signs]
    # this concatenation means the sign list order matters
    sign_data = [match_num] + red_teams + [match_time] + blue_teams

    threads = []
    for idx, conn in enumerate(connections):
        # use sign name as connection if sim
        conn = SimpleNamespace(host=conn['name']) if is_sim else conn
        t = Thread(target=update_sign, args=(conn, sign_data[idx]))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()


def get_local_matches():
    return json.load(open(event + '_matches.json'))


def get_next_team_match(team, event):
    team_matches = get_local_matches() if offline else sorted(tba.team_matches(team, event),
                                                              key=lambda match: match['time'])
    next_match = team_matches[-1]

    if offline:
        next_match = team_matches[match_idx]
    else:
        for match in team_matches:
            if match['post_result_time'] is None:
                next_match = match
                break
    return next_match


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


def get_current_event_match(event):
    event_matches = sorted(tba.event_matches(
        event), key=lambda match: match['time'])
    next_match = event_matches[-1]
    for match in event_matches:
        if match['post_result_time'] is None:
            next_match = match
            break
    return next_match


def update_now_playing():
    signs = [sign for sign in settings['signs'] if 'info' in sign['name']]
    connections = signs if is_sim else [Connection(
        'inova@'+sign['name'], connect_kwargs={'password': sign['pass']}) for sign in signs]
    arg_list = [displayed_match, pred_time]

    threads = []
    for idx, conn in enumerate(connections):
        # use sign name as connection if sim
        conn = SimpleNamespace(host=conn['name']) if is_sim else conn
        t = Thread(target=update_sign, args=(conn, arg_list[idx]))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()


def format_time(next_match):
    try:
        return time.strftime('%_I:%M', time.localtime(next_match['predicted_time']))
    except:
        # microsoft sucks
        return time.strftime('%#I:%M', time.localtime(next_match['predicted_time']))


def check_match_status():
    global displayed_match, red_teams, blue_teams, current_match, pred_time
    next_match = get_next_team_match(settings['team'], event)
    pred_time = format_time(next_match)
    new_match = next_match['comp_level'].upper(
    ) + str(next_match['match_number']) != displayed_match
    if new_match:
        displayed_match = next_match['comp_level'].upper(
        ) + str(next_match['match_number'])

    if not offline:
        new_curr = get_current_event_match(event)
        now_playing = new_curr['comp_level'].upper() + \
            str(new_curr['match_number'])
        if now_playing != current_match and not new_match:
            current_match = now_playing
            update_now_playing()
            print('updated now playing to', current_match)

    new_red_teams = format_team_keys(
        next_match['alliances']['red']['team_keys']) != red_teams
    new_blue_teams = format_team_keys(
        next_match['alliances']['blue']['team_keys']) != blue_teams

    if new_match or new_red_teams or new_blue_teams:
        red_teams = format_team_keys(
            next_match['alliances']['red']['team_keys'])
        blue_teams = format_team_keys(
            next_match['alliances']['blue']['team_keys'])

        update_displays(red_teams, blue_teams, displayed_match, pred_time)


def get_local_names():
    return json.load(open(event + '_teams.json'))


def get_team_names():
    global team_names

    raw_teams = get_local_names() if offline else tba.event_teams(event)
    for tm in raw_teams:
        base_name = tm['nickname']
        clean_name = ''.join([i if ord(i) < 128 else '' for i in base_name])
        team_names[str(tm['team_number'])
                   ] = clean_name[:settings['name_lim']]


def offline_update(key):
    global match_idx
    if key.name == ']':
        match_idx += 1
        check_match_status()
    elif key.name == '[':
        if match_idx > 0:
            match_idx -= 1
        else:
            match_idx = 0
        check_match_status()


def build_local_names():
    json.dump(tba.event_teams(event), open(event + '_teams.json', 'w'))


def build_local_matches():
    matches = sorted(tba.team_matches(team, event),
                     key=lambda match: match['time'])
    json.dump(matches,
              open(event + '_matches.json', 'w'))


def main():
    get_team_names()
    while True:
        if offline:
            check_match_status()
            keyboard.on_press(offline_update)
            keyboard.wait()
        else:
            check_match_status()
            time.sleep(settings['delay'])


if __name__ == "__main__":
    main()
