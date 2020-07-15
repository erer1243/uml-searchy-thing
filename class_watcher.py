#!/usr/bin/env python3
import sys
from time import sleep
from requests import get
from twilio.rest import Client
from pprint import pprint

# twilio stuff
# ============
sid    = "Your sid here"
token  = "Your token here"
from_n = "your from phone number here (twilio number)"
to_n   = "your cell phone number here (both numbers must begin with a + like +16171234567)"
client = Client(sid, token)

# class search stuff
# ==================
# I don't really remember how I got the search URLs. I think you can go to student dashboard class search,
# do a search, then copy the query parameters from THAT url (everything after ?) onto the end of this:
# https://www.uml.edu/student-dashboard/api/ClassSchedule/RealTime/Search/

# So for example I went to uml.edu/now > class search, made a search for ACCT 1234, and the url bar shows this:
# https://www.uml.edu/student-dashboard#class-search/search?term=3010&subjects=ACCT&partialCatalogNumber=1234
# So I copy the parameters onto the end of the first url, and I get this
# https://www.uml.edu/student-dashboard/api/ClassSchedule/RealTime/Search/?term=3010&subjects=ACCT&partialCatalogNumber=1234
# and I think that is a valid url. At least it appears to be. 
# IDK try it. I included the urls I used last semester as an example.

search_urls = [
    # College Writing II
    #"https://www.uml.edu/student-dashboard/api/ClassSchedule/RealTime/Search/?term=2930&subjects=ENGL&partialCatalogNumber=1020&meetingTimeModes=1%2C2%2C3&campuses=UMLNORTH"
    #"https://www.uml.edu/student-dashboard/api/ClassSchedule/RealTime/Search/?term=2930&subjects=ENGL&partialCatalogNumber=1020&meetingTimeModes=1%2C2%2C3"
    #"https://www.uml.edu/student-dashboard/api/ClassSchedule/RealTime/Search/?term=2930&subjects=ENGL&partialCatalogNumber=1020&enrollmentStatusMode=1&daySchoolBlackboardEnabledOnly=1"
]
query_mins = 3
max_tries  = 4

def send_message(message):
    print("Sending message", message)
    try:
        pass
        client.messages.create(to=to_n, from_=from_n, body=message)
    except Exception as e:
        print(e)
    sleep(3)

def digest_class(class_data):
    try:
        details = class_data['Details']
        title = details['CourseTitle']
        capacity = details['EnrollmentCapacity']
        enrollment = details['EnrollmentTotal']
        enrollment_str = "{}/{}".format(enrollment, capacity)
        status = details['EnrollmentStatus']['Description']
        number = details['ClassNumber']
        meeting_data = class_data['Meetings'][0]
        if len(meeting_data['Instructors']) == 0:
            prof_name = "TBA"
        else:
            prof_data = meeting_data['Instructors'][0]['Person']
            prof_name = "{} {}".format(prof_data['FirstName'], prof_data['LastName'])
        location = meeting_data['Facility']['ShortDescription']
        meet_days = meeting_data['DaysString']
        meet_time = "{} to {}".format(meeting_data['StartTimeFormatted'], meeting_data['EndTimeFormatted'])

        return (title, number, prof_name, enrollment_str,
                status, location, meet_days, meet_time)
    except Exception as e:
        print("Error digesting class")
        print("=====================")
        print(e)
        print("=====================")
        pprint(class_data)
        print("=====================")
        return None

def is_honors(class_data):
    for attr in class_data['Attributes']:
        if attr['Value']['Code'] == 'HONORS':
            return True
    return False

def send_update_message(digested_class):
    send_message('|'.join(str(x) for x in digested_class))

def send_update_message(old_class, new_class):
    s = ""
    for i in range(len(old_class)):
        if old_class[i] == new_class[i]:
            s += str(old_class[i])
        else:
            s += "{} -> {}".format(old_class[i], new_class[i])
        s += "|"

    send_message(s[:-1])

def get_classes(url, accept_honors):
    tries = 1
    data  = None
    while tries < max_tries:
        tries += 1
        try:
            data = get(url).json()
            break
        except Exception as e:
            print("Error querying class search API. Trying", max_tries-tries, "more times")
            print(e)
            sleep(2)

    if data == None:
        return None

    try:
        classes = data['data']['Classes']
    except:
        print("Query succeeded but didn't contain class data.")
        return None

    accum = []
    for c in classes:
        if (not accept_honors) and is_honors(c):
            continue
        digested = digest_class(c)
        if digested:
            accum.append(digested)

    return sorted(accum, key=lambda c: c[1])

# Collect initial class information
# =================================
print("COLLECTING INITIAL CLASS INFO")
cur_classes = []
for url in search_urls:
    class_data = get_classes(url, False)
    if class_data == None:
        print("Aborting")
        sys.exit(1)
    cur_classes = class_data

pprint(cur_classes)

# Main loop
# =========
send_message("Class watcher started")
loops = 1
while True:
    print(loops, "QUERYING FOR CHANGES")
    loops += 1
    for i, url in enumerate(search_urls):
        new_classes = get_classes(url, False)
        if new_classes == None:
            send_message("ERROR get_classes failed!")
            continue

        diff = False

        # Check if there are any new classes
        if len(new_classes) != len(cur_classes):
            diff = True

        if len(new_classes) > len(cur_classes):
            send_message("{} new class(es)".format(len(new_classes)-len(cur_classes)))
            for i in range(len(cur_classes), len(new_classes)):
                send_message(str(new_classes[i]))
        elif len(new_classes) < len(cur_classes):
            print("{} CLASSES REDUCED TO {}".format(len(cur_classes), len(new_classes)))

        # Check if any classes have changed
        changes = []
        for i in range(min(len(cur_classes), len(new_classes))):
            if new_classes[i] != cur_classes[i]:
                changes.append(i)
                diff = True

        if len(changes) != 0:
            send_message("{} class update(s)".format(len(changes)))
            for i in changes:
                send_update_message(cur_classes[i], new_classes[i])

        if diff:
            cur_classes = new_classes

    try:
        sleep(query_mins * 60)
    except KeyboardInterrupt:
        print("Exiting")
        sys.exit(0)
