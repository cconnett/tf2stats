create temporary table if not exists pp as select * from pugplayers;
create index p4 on pp (pug, player);
create index p3 on pp (player);
create index pc on pp (player, class);

create temporary table if not exists p as select * from pugs;
create index p1 on p (id);

create temporary table _summary as
select r.pug pug, pp.team team, e.srcplayer player,
pp.class class, e.type type, vicpp.class vicclass,
count(*) n, pp.totaltime/60.0 m,
(strftime('%s', p.end) - strftime('%s', p.begin))/60.0 matchtime

from events e join rounds r on e.round = r.id
join pp on r.pug = pp.pug and e.srcplayer = pp.player
join p on pp.pug = p.id
left outer join pp vicpp on r.pug = vicpp.pug and e.vicplayer = vicpp.player
where r.type = 'normal' and e.type = 5
group by r.pug, e.srcplayer, pp.class, e.type, vicpp.class
order by r.pug, pp.team, e.srcplayer, e.type, vicpp.class
;
create index _idx_ppctv on _summary (pug, player, class, type, vicclass);
create index _idx_pctv on _summary (player, class, type, vicclass);

create temporary table _deaths as
select r.pug pug, pp.team team, e.vicplayer player,
pp.class class, srcpp.class srcclass,
count(*) n, pp.totaltime/60.0 m,
(strftime('%s', p.end) - strftime('%s', p.begin))/60.0 matchtime

from events e join rounds r on e.round = r.id
join pp on r.pug = pp.pug and e.srcplayer = pp.player
join p on pp.pug = p.id
left outer join pp srcpp on r.pug = srcpp.pug and e.srcplayer = srcpp.player
where r.type = 'normal' and e.type = 5
group by r.pug, e.vicplayer, pp.class, srcpp.class
order by r.pug, pp.team, e.srcplayer, srcpp.class
;
create index _idx_ppcts on _deaths (pug, player, class, srcclass);
create index _idx_pcts on _deaths (player, class, srcclass);

--Range factor setup
--Overall stats for all matches
create temporary table _classtime as
select class, sum(totaltime) classtime
from pp
where class != 'medic'
group by class;

create temporary table _classtime_factor as
select class, (select max(cast(classtime as float)) from _classtime) / classtime cf
from _classtime;

create temporary table _kills as
select pp.class class, count(*) n
from events e join rounds r on e.round = r.id join pp on e.srcplayer = pp.player and r.pug = pp.pug
where e.type = 5 and pp.class != 'medic' and r.type = 'normal'
group by pp.class;

create temporary table _assists as
select pp.class class, count(*) n
from events e join rounds r on e.round = r.id join pp on e.srcplayer = pp.player and r.pug = pp.pug
where e.type = 6 and pp.class != 'medic' and r.type = 'normal'
group by pp.class;

create temporary table _p as
select k.class, k.n + 0.5 * a.n p
from _kills k join _assists a on k.class = a.class;

create temporary table _rfbase as
select _cf.class class, p * cf rfbase
from _classtime_factor _cf join _p on _cf.class = _p.class;

create temporary table _rfpct as
select pp.pug pug, pp.team team, pp.class class, rfbase,
       rfbase / (select sum(rfbase) from pp thisPP join _rfbase on thisPP.class = _rfbase.class
                  where thisPP.pug = pp.pug and thisPP.team = pp.team) rfpct
from pp join _rfbase on pp.class = _rfbase.class
where pp.class != 'medic'
group by pp.pug, pp.team, pp.class;
create index rfpct_ptc on _rfpct (pug, team, class);

--select * from _rfpct;

--Individual player stats (by pug and player)
create temporary table _playerk as
select pp.pug pug, pp.player player, pp.class class, count(*) n
from events e join rounds r on e.round = r.id join pp on e.srcplayer = pp.player and r.pug = pp.pug
where e.type = 5 and pp.class != 'medic' and r.type = 'normal'
group by pp.pug, pp.player;
create index pkpp on _playerk (pug, player);

create temporary table _playera as
select pp.pug pug, pp.player player, pp.class class, count(*) n
from events e join rounds r on e.round = r.id join pp on e.srcplayer = pp.player and r.pug = pp.pug
where e.type = 5 and pp.class != 'medic' and r.type = 'normal'
group by pp.pug, pp.player;
create index papp on _playera (pug, player);

create temporary table _playerp as
select k.pug pug, pp.team team, k.player player, k.class class,
       (k.n + 0.5 * a.n)
       * max((select strftime('%s', pugs.end) - strftime('%s', pugs.begin)
                from p pugs where pugs.id = k.pug)
             / cast(totaltime as float), 1) p,
       max((select strftime('%s', pugs.end) - strftime('%s', pugs.begin)
              from p pugs where pugs.id = k.pug)
           / cast(totaltime as float), 1) adjustment
from _playerk k join _playera a on k.pug = a.pug and k.player = a.player join pp on pp.pug = k.pug and pp.player = k.player
where pp.player in (select thisPP.player from pp thisPP where thisPP.pug = pp.pug
                      group by thisPP.pug, thisPP.player
                      order by sum(totaltime) desc
                      limit 12);

--select * from _playerp where pug = 84;
--select player, class from pp

--Team frag counts (by pug and team)
create temporary table _teamk as
select r.pug pug, l.team team, count(*) n
from events e join rounds r on e.round = r.id join lives l on e.srclife = l.id
              join pp on r.pug = pp.pug and l.player = pp.player
where e.type = 5 and pp.class != 'medic' and r.type = 'normal'
group by r.pug, l.team;
create index tkpt on _teamk (pug, team);

create temporary table _teama as
select pp.pug pug, pp.team team, count(*) n
from events e join rounds r on e.round = r.id join lives l on e.srclife = l.id
              join pp on r.pug = pp.pug and l.player = pp.player
where e.type = 6 and pp.class != 'medic' and r.type = 'normal'
group by pp.pug, pp.team;
create index tapt on _teama (pug, team);

create temporary table _teamp as
select k.pug pug, k.team team, k.n + 0.5 * a.n p
from _teamk k join _teama a on k.pug = a.pug and k.team = a.team;

--select * from _teamp;
--End range factor setup.

select pug, team, player,

(case when pp.team = 'Blue' then bluescore when pp.team = 'Red' then redscore else null end) p,
(select sum(winner = pp.team) - sum(winner != pp.team) from rounds where rounds.pug = pp.pug) dp,
(case when pp.team = 'Blue'
       then (case when bluescore > redscore then bluescore + 4 - redscore else bluescore end)
       else (case when redscore > bluescore then redscore + 4 - bluescore else redscore end)
 end) bp,

(select
avg(_playerp.p / _teamp.p / rfpct) rf
--sum(_playerp.p) / sum(_teamp.p) / rfpct rfWeighted
from _playerp join _teamp on _playerp.pug = _teamp.pug and _playerp.team = _teamp.team
              join _rfpct on _playerp.pug = _rfpct.pug and _playerp.team = _rfpct.team and _playerp.class = _rfpct.class
join players on _playerp.player = players.steamid
where _playerp.player = pp.player and _playerp.pug != pp.pug
group by player) rf,


pp.class = 'scout' isscout,
(select coalesce(sum(m), 0) from _summary k where k.pug != pp.pug and k.player = pp.player and k.class = 'scout' and k.type = 5 and k.vicclass = 'scout') m1,
(select coalesce(sum(n), 0) from _summary k where k.pug != pp.pug and k.player = pp.player and k.class = 'scout' and k.type = 5) k1,
(select coalesce(sum(n), 0) from _summary k where k.pug != pp.pug and k.player = pp.player and k.class = 'scout' and k.type = 5 and k.vicclass = 'scout') k11,
(select coalesce(sum(n), 0) from _summary k where k.pug != pp.pug and k.player = pp.player and k.class = 'scout' and k.type = 5 and k.vicclass = 'soldier') k12,
(select coalesce(sum(n), 0) from _summary k where k.pug != pp.pug and k.player = pp.player and k.class = 'scout' and k.type = 5 and k.vicclass = 'demoman') k14,
(select coalesce(sum(n), 0) from _summary k where k.pug != pp.pug and k.player = pp.player and k.class = 'scout' and k.type = 5 and k.vicclass = 'medic') k17,
(select coalesce(sum(n), 0) from _summary k where k.pug != pp.pug and k.player = pp.player and k.class = 'scout' and k.type = 6) a1,
(select coalesce(sum(n), 0) from _summary k where k.pug != pp.pug and k.player = pp.player and k.class = 'scout' and k.type = 6 and k.vicclass = 'scout') a11,
(select coalesce(sum(n), 0) from _summary k where k.pug != pp.pug and k.player = pp.player and k.class = 'scout' and k.type = 6 and k.vicclass = 'soldier') a12,
(select coalesce(sum(n), 0) from _summary k where k.pug != pp.pug and k.player = pp.player and k.class = 'scout' and k.type = 6 and k.vicclass = 'demoman') a14,
(select coalesce(sum(n), 0) from _summary k where k.pug != pp.pug and k.player = pp.player and k.class = 'scout' and k.type = 6 and k.vicclass = 'medic') a17,
(select coalesce(sum(n), 0) from _deaths k where k.pug != pp.pug and k.player = pp.player and k.class = 'scout') d1,
(select coalesce(sum(n), 0) from _deaths k where k.pug != pp.pug and k.player = pp.player and k.class = 'scout' and k.srcclass = 'scout') d11,
(select coalesce(sum(n), 0) from _deaths k where k.pug != pp.pug and k.player = pp.player and k.class = 'scout' and k.srcclass = 'soldier') d12,
(select coalesce(sum(n), 0) from _deaths k where k.pug != pp.pug and k.player = pp.player and k.class = 'scout' and k.srcclass = 'demoman') d14,
(select coalesce(sum(n), 0) from _deaths k where k.pug != pp.pug and k.player = pp.player and k.class = 'scout' and k.srcclass = 'medic') d17,

pp.class = 'soldier' issoldier,
(select coalesce(sum(m), 0) from _summary k where k.pug != pp.pug and k.player = pp.player and k.class = 'soldier' and k.type = 5 and k.vicclass = 'scout') m2,
(select coalesce(sum(n), 0) from _summary k where k.pug != pp.pug and k.player = pp.player and k.class = 'soldier' and k.type = 5) k2,
(select coalesce(sum(n), 0) from _summary k where k.pug != pp.pug and k.player = pp.player and k.class = 'soldier' and k.type = 5 and k.vicclass = 'scout') k21,
(select coalesce(sum(n), 0) from _summary k where k.pug != pp.pug and k.player = pp.player and k.class = 'soldier' and k.type = 5 and k.vicclass = 'soldier') k22,
(select coalesce(sum(n), 0) from _summary k where k.pug != pp.pug and k.player = pp.player and k.class = 'soldier' and k.type = 5 and k.vicclass = 'demoman') k24,
(select coalesce(sum(n), 0) from _summary k where k.pug != pp.pug and k.player = pp.player and k.class = 'soldier' and k.type = 5 and k.vicclass = 'medic') k27,
(select coalesce(sum(n), 0) from _summary k where k.pug != pp.pug and k.player = pp.player and k.class = 'soldier' and k.type = 6) a2,
(select coalesce(sum(n), 0) from _summary k where k.pug != pp.pug and k.player = pp.player and k.class = 'soldier' and k.type = 6 and k.vicclass = 'scout') a21,
(select coalesce(sum(n), 0) from _summary k where k.pug != pp.pug and k.player = pp.player and k.class = 'soldier' and k.type = 6 and k.vicclass = 'soldier') a22,
(select coalesce(sum(n), 0) from _summary k where k.pug != pp.pug and k.player = pp.player and k.class = 'soldier' and k.type = 6 and k.vicclass = 'demoman') a24,
(select coalesce(sum(n), 0) from _summary k where k.pug != pp.pug and k.player = pp.player and k.class = 'soldier' and k.type = 6 and k.vicclass = 'medic') a27,
(select coalesce(sum(n), 0) from _deaths k where k.pug != pp.pug and k.player = pp.player and k.class = 'soldier') d2,
(select coalesce(sum(n), 0) from _deaths k where k.pug != pp.pug and k.player = pp.player and k.class = 'soldier' and k.srcclass = 'scout') d21,
(select coalesce(sum(n), 0) from _deaths k where k.pug != pp.pug and k.player = pp.player and k.class = 'soldier' and k.srcclass = 'soldier') d22,
(select coalesce(sum(n), 0) from _deaths k where k.pug != pp.pug and k.player = pp.player and k.class = 'soldier' and k.srcclass = 'demoman') d24,
(select coalesce(sum(n), 0) from _deaths k where k.pug != pp.pug and k.player = pp.player and k.class = 'soldier' and k.srcclass = 'medic') d27,

pp.class = 'demoman' isdemoman,
(select coalesce(sum(m), 0) from _summary k where k.pug != pp.pug and k.player = pp.player and k.class = 'demoman' and k.type = 5 and k.vicclass = 'scout') m4,
(select coalesce(sum(n), 0) from _summary k where k.pug != pp.pug and k.player = pp.player and k.class = 'demoman' and k.type = 5) k4,
(select coalesce(sum(n), 0) from _summary k where k.pug != pp.pug and k.player = pp.player and k.class = 'demoman' and k.type = 5 and k.vicclass = 'scout') k41,
(select coalesce(sum(n), 0) from _summary k where k.pug != pp.pug and k.player = pp.player and k.class = 'demoman' and k.type = 5 and k.vicclass = 'soldier') k42,
(select coalesce(sum(n), 0) from _summary k where k.pug != pp.pug and k.player = pp.player and k.class = 'demoman' and k.type = 5 and k.vicclass = 'demoman') k44,
(select coalesce(sum(n), 0) from _summary k where k.pug != pp.pug and k.player = pp.player and k.class = 'demoman' and k.type = 5 and k.vicclass = 'medic') k47,
(select coalesce(sum(n), 0) from _summary k where k.pug != pp.pug and k.player = pp.player and k.class = 'demoman' and k.type = 6) a4,
(select coalesce(sum(n), 0) from _summary k where k.pug != pp.pug and k.player = pp.player and k.class = 'demoman' and k.type = 6 and k.vicclass = 'scout') a41,
(select coalesce(sum(n), 0) from _summary k where k.pug != pp.pug and k.player = pp.player and k.class = 'demoman' and k.type = 6 and k.vicclass = 'soldier') a42,
(select coalesce(sum(n), 0) from _summary k where k.pug != pp.pug and k.player = pp.player and k.class = 'demoman' and k.type = 6 and k.vicclass = 'demoman') a44,
(select coalesce(sum(n), 0) from _summary k where k.pug != pp.pug and k.player = pp.player and k.class = 'demoman' and k.type = 6 and k.vicclass = 'medic') a47,
(select coalesce(sum(n), 0) from _deaths k where k.pug != pp.pug and k.player = pp.player and k.class = 'demoman') d4,
(select coalesce(sum(n), 0) from _deaths k where k.pug != pp.pug and k.player = pp.player and k.class = 'demoman' and k.srcclass = 'scout') d41,
(select coalesce(sum(n), 0) from _deaths k where k.pug != pp.pug and k.player = pp.player and k.class = 'demoman' and k.srcclass = 'soldier') d42,
(select coalesce(sum(n), 0) from _deaths k where k.pug != pp.pug and k.player = pp.player and k.class = 'demoman' and k.srcclass = 'demoman') d44,
(select coalesce(sum(n), 0) from _deaths k where k.pug != pp.pug and k.player = pp.player and k.class = 'demoman' and k.srcclass = 'medic') d47,

pp.class = 'medic' ismedic,
(select coalesce(sum(m), 0) from _summary k where k.pug != pp.pug and k.player = pp.player and k.class = 'medic' and k.type = 5 and k.vicclass = 'scout') m7,
(select coalesce(sum(n), 0) from _summary k where k.pug != pp.pug and k.player = pp.player and k.class = 'medic' and k.type = 5) k7,
(select coalesce(sum(n), 0) from _summary k where k.pug != pp.pug and k.player = pp.player and k.class = 'medic' and k.type = 5 and k.vicclass = 'scout') k71,
(select coalesce(sum(n), 0) from _summary k where k.pug != pp.pug and k.player = pp.player and k.class = 'medic' and k.type = 5 and k.vicclass = 'soldier') k72,
(select coalesce(sum(n), 0) from _summary k where k.pug != pp.pug and k.player = pp.player and k.class = 'medic' and k.type = 5 and k.vicclass = 'demoman') k74,
(select coalesce(sum(n), 0) from _summary k where k.pug != pp.pug and k.player = pp.player and k.class = 'medic' and k.type = 5 and k.vicclass = 'medic') k77,
(select coalesce(sum(n), 0) from _summary k where k.pug != pp.pug and k.player = pp.player and k.class = 'medic' and k.type = 6) a7,
(select coalesce(sum(n), 0) from _summary k where k.pug != pp.pug and k.player = pp.player and k.class = 'medic' and k.type = 6 and k.vicclass = 'scout') a71,
(select coalesce(sum(n), 0) from _summary k where k.pug != pp.pug and k.player = pp.player and k.class = 'medic' and k.type = 6 and k.vicclass = 'soldier') a72,
(select coalesce(sum(n), 0) from _summary k where k.pug != pp.pug and k.player = pp.player and k.class = 'medic' and k.type = 6 and k.vicclass = 'demoman') a74,
(select coalesce(sum(n), 0) from _summary k where k.pug != pp.pug and k.player = pp.player and k.class = 'medic' and k.type = 6 and k.vicclass = 'medic') a77,
(select coalesce(sum(n), 0) from _deaths k where k.pug != pp.pug and k.player = pp.player and k.class = 'medic') d7,
(select coalesce(sum(n), 0) from _deaths k where k.pug != pp.pug and k.player = pp.player and k.class = 'medic' and k.srcclass = 'scout') d71,
(select coalesce(sum(n), 0) from _deaths k where k.pug != pp.pug and k.player = pp.player and k.class = 'medic' and k.srcclass = 'soldier') d72,
(select coalesce(sum(n), 0) from _deaths k where k.pug != pp.pug and k.player = pp.player and k.class = 'medic' and k.srcclass = 'demoman') d74,
(select coalesce(sum(n), 0) from _deaths k where k.pug != pp.pug and k.player = pp.player and k.class = 'medic' and k.srcclass = 'medic') d77,
NULL

from pp join p on pp.pug = p.id
group by pp.pug, pp.player
having pp.player in (select thisPP.player from pp thisPP where thisPP.pug = pp.pug
                      group by thisPP.pug, thisPP.player
                      order by sum(totaltime) desc
                      limit 12)
order by pug, team, player;
