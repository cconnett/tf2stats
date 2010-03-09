create temporary table if not exists _playercore as
select player, pug,
(select coalesce(sum(m), 0) from _summary k where k.pug != pp.pug and k.player = pp.player and k.type = 5 and k.class != 'medic' and k.vicclass = 'scout') m,
(select coalesce(sum(n), 0) from _summary k where k.pug != pp.pug and k.player = pp.player and k.type = 5 and k.class != 'medic') k,
(select coalesce(sum(n), 0) from _summary k where k.pug != pp.pug and k.player = pp.player and k.type = 6 and k.class != 'medic') a,
(select coalesce(sum(n), 0) from _deaths k where k.pug != pp.pug and k.player = pp.player and k.class != 'medic') d
from pp;
create index _pc_pp on _playercore (player, pug);

--create table if not exists playervitals as
select pp.pug, r.id round, pp.team, pp.player,
-- (case when pp.team = 'Blue' then bluescore when pp.team = 'Red' then redscore else null end) p,
-- (select sum(winner = pp.team) - sum(winner != pp.team) from rounds where rounds.pug = pp.pug) dp,
-- (case when pp.team = 'Blue'
--        then (case when bluescore > redscore then bluescore + 4 - redscore else bluescore end)
--        else (case when redscore > bluescore then redscore + 4 - bluescore else redscore end)
--  end) bp,

(select rf from _rf where player = pp.player and pug = pp.pug) rf,
NULL gwp,
NULL teamgwp,
NULL oppgwp,
--(select rf from _teamrf where team = pp.team and pug = p.id) teamrf,
--(select rf from _teamrf where team != pp.team and pug = p.id) opprf,

(select k/m from _playercore pc where pc.pug = pp.pug and pc.player = pp.player) kpm,
(select d/m from _playercore pc where pc.pug = pp.pug and pc.player = pp.player) dpm,
(select a/m from _playercore pc where pc.pug = pp.pug and pc.player = pp.player) apm,

(r.winner = pp.team) win

from pp join p on pp.pug = p.id
left outer join rounds r on r.pug = pp.pug
where r.type = 'normal' and pp.class != 'medic'
group by round, pp.team, pp.player
having pp.player in (select thisPP.player from pp thisPP where thisPP.pug = pp.pug
                      group by thisPP.pug, thisPP.player
                      order by sum(totaltime) desc
                      limit 12)
order by pp.player, r.id, pp.team;
