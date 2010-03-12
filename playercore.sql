create temporary table if not exists _playercore as
select player, pug,
(select coalesce(sum(m), 0) from _summary k where k.pug != pp.pug and k.player = pp.player and k.type = 5 and k.class != 'medic' and k.vicclass = 'scout') m,
(select coalesce(sum(n), 0) from _summary k where k.pug != pp.pug and k.player = pp.player and k.type = 5 and k.class != 'medic') k,
(select coalesce(sum(n), 0) from _summary k where k.pug != pp.pug and k.player = pp.player and k.type = 6 and k.class != 'medic') a,
(select coalesce(sum(n), 0) from _deaths k where k.pug != pp.pug and k.player = pp.player and k.class != 'medic') d
from pp;
create index _pc_pp on _playercore (player, pug);

create table if not exists teamGWPs (pug int, team text, gwp float);
create index if not exists tgwp_pt on teamGWPs (pug, team);

drop table if exists playervitals;
create table if not exists playervitals as
select pp.pug pug, r.id round, pp.team team, pp.player player,

NULL gwp,
NULL teamgwp,
NULL oppgwp,
NULL adjustment,

(select cast(k as float)/m from _playercore pc where pc.pug = pp.pug and pc.player = pp.player) kpm,
(select cast(d as float)/m from _playercore pc where pc.pug = pp.pug and pc.player = pp.player) dpm,
(select cast(a as float)/m from _playercore pc where pc.pug = pp.pug and pc.player = pp.player) apm,
(select cast(k as float)/d from _playercore pc where pc.pug = pp.pug and pc.player = pp.player) kdr,

(select rf from _rf where player = pp.player and pug = pp.pug) rf,

(r.winner = pp.team) win

from pp
left outer join (select * from rounds union all select * from _bonus_rounds) r on r.pug = pp.pug
where r.type in ('normal', 'bonus') and pp.class != 'medic'
group by round, pp.player
having pp.player in (select thisPP.player from pp thisPP where thisPP.pug = pp.pug
                      group by thisPP.pug, thisPP.player
                      order by sum(totaltime) desc
                      limit 12)
order by pp.player, pp.pug;
create index if not exists pv_pt on playervitals (player, pug, team);
