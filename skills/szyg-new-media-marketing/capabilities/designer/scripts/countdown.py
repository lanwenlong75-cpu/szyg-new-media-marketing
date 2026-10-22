import argparse,json,math
from datetime import datetime
def calculate(deadline_text, now_text):
    deadline=datetime.fromisoformat(deadline_text);now=datetime.fromisoformat(now_text)
    if deadline.tzinfo is None or now.tzinfo is None:raise ValueError('截止与参考时间必须带时区，例如2026-10-20T20:00:00+08:00')
    seconds=(deadline-now).total_seconds();local_now=now.astimezone(deadline.tzinfo)
    return {'deadline':deadline.isoformat(),'now':local_now.isoformat(),'expired':seconds<=0,'secondsRemaining':max(0,seconds),'calendarDays':max(0,(deadline.date()-local_now.date()).days),'durationDaysCeiling':max(0,math.ceil(seconds/86400))}

if __name__=='__main__':
    p=argparse.ArgumentParser(description='计算带时区的截止时间，区分自然日差与剩余时长向上取整')
    p.add_argument('--deadline',required=True);p.add_argument('--now',required=True)
    a=p.parse_args()
    try:print(json.dumps(calculate(a.deadline,a.now),ensure_ascii=False))
    except ValueError as e:raise SystemExit(str(e))
