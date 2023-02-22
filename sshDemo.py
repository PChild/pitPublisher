from fabric import Connection

sign = {"name": "spare1", "pass": "slim0d5"}

conn = Connection('inova@'+sign['name'], connect_kwargs={'password':sign['pass']})
conn.run("localmsgs delete -f ALL")

color = 'red'
text = '_1:  401'
conn.run("localmsgs compose -c %s -d 0 -f test.llm -p appear -s 16 -t '%s'" % (color, text), hide=True)
conn.close()
