create temporary view if not exists _teamstats as

select p.id pug, t.team team,

--Time
(select sum(strftime('%s', rounds.end) - strftime('%s', rounds.begin))
from rounds where rounds.type = 'normal' and rounds.pug = p.id)/60.0 m,

--Score
(case when team = 'Blue' then bluescore else redscore end) p,
(case when team = 'Blue'
       then (case when bluescore > redscore then bluescore + 4 - redscore else bluescore end)
       else (case when redscore > bluescore then redscore + 4 - bluescore else redscore end)
 end) bp,

--Kills
(select count(*) from events e join rounds r on e.round = r.id join lives l on e.srclife = l.id
 where r.type = 'normal' and e.type = 5 and r.pug = p.id and l.team = t.team and l.class = 'scout') k1,
(select count(*) from events e join rounds r on e.round = r.id join lives l on e.srclife = l.id
 where r.type = 'normal' and e.type = 5 and r.pug = p.id and l.team = t.team and l.class = 'soldier') k2,
(select count(*) from events e join rounds r on e.round = r.id join lives l on e.srclife = l.id
 where r.type = 'normal' and e.type = 5 and r.pug = p.id and l.team = t.team and l.class = 'demoman') k4,
(select count(*) from events e join rounds r on e.round = r.id join lives l on e.srclife = l.id
 where r.type = 'normal' and e.type = 5 and r.pug = p.id and l.team = t.team and l.class not in ('scout','soldier','demoman')) ko,
(select count(*) from events e join rounds r on e.round = r.id join lives l on e.srclife = l.id
 where r.type = 'normal' and e.type = 5 and r.pug = p.id and l.team = t.team) k,
--Assists
(select count(*) from events e join rounds r on e.round = r.id join lives l on e.srclife = l.id
 where r.type = 'normal' and e.type = 6 and r.pug = p.id and l.team = t.team and l.class = 'scout') a1,
(select count(*) from events e join rounds r on e.round = r.id join lives l on e.srclife = l.id
 where r.type = 'normal' and e.type = 6 and r.pug = p.id and l.team = t.team and l.class = 'soldier') a2,
(select count(*) from events e join rounds r on e.round = r.id join lives l on e.srclife = l.id
 where r.type = 'normal' and e.type = 6 and r.pug = p.id and l.team = t.team and l.class = 'demoman') a4,
(select count(*) from events e join rounds r on e.round = r.id join lives l on e.srclife = l.id
 where r.type = 'normal' and e.type = 6 and r.pug = p.id and l.team = t.team and l.class = 'medic') a7,
(select count(*) from events e join rounds r on e.round = r.id join lives l on e.srclife = l.id
 where r.type = 'normal' and e.type = 6 and r.pug = p.id and l.team = t.team and l.class not in ('scout','soldier','demoman','medic')) ao,
(select count(*) from events e join rounds r on e.round = r.id join lives l on e.srclife = l.id
 where r.type = 'normal' and e.type = 6 and r.pug = p.id and l.team = t.team) a,

--Deaths
(select count(*) from events e join rounds r on e.round = r.id join lives l on e.viclife = l.id
 where r.type = 'normal' and e.type = 5 and r.pug = p.id and l.team = t.team and l.class = 'scout') d1,
(select count(*) from events e join rounds r on e.round = r.id join lives l on e.viclife = l.id
 where r.type = 'normal' and e.type = 5 and r.pug = p.id and l.team = t.team and l.class = 'soldier') d2,
(select count(*) from events e join rounds r on e.round = r.id join lives l on e.viclife = l.id
 where r.type = 'normal' and e.type = 5 and r.pug = p.id and l.team = t.team and l.class = 'demoman') d4,
(select count(*) from events e join rounds r on e.round = r.id join lives l on e.viclife = l.id
 where r.type = 'normal' and e.type = 5 and r.pug = p.id and l.team = t.team and l.class = 'medic') d7,
(select count(*) from events e join rounds r on e.round = r.id join lives l on e.viclife = l.id
 where r.type = 'normal' and e.type = 5 and r.pug = p.id and l.team = t.team and l.class not in ('scout','soldier','demoman','medic')) do,
(select count(*) from events e join rounds r on e.round = r.id join lives l on e.viclife = l.id
 where r.type = 'normal' and e.type = 5 and r.pug = p.id and l.team = t.team) d,

--Invulns
(select count(*) from events e join rounds r on e.round = r.id join lives l on e.srclife = l.id
 where r.type = 'normal' and e.type = 3 and r.pug = p.id and l.team = t.team) i

from teams t join pugs p;

select pug, team, m, p/m ppm, bp/m bppm, k1/m k1pm, k2/m k2pm, k4/m k4pm, ko/m kopm, k/m kpm, a1/m a1pm, a2/m a2pm, a4/m a4pm, a7/m a7pm, ao/m aopm, a/m apm, d1/m d1pm, d2/m d2pm, d4/m d4pm, d7/m d7pm, do/m dopm, d/m dpm, i/m ipm
from _teamstats;
drop view _teamstats;
