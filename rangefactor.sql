create temporary table if not exists pp as select * from pugplayers;
create index p4 on pp (pug, player);
create index p3 on pp (player);
create index pc on pp (player, class);

create temporary table if not exists p as select * from pugs;
create index p1 on p (id);

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

select --_playerp.pug, _playerp.team,
--name,
_playerp.player,
--_playerp.p, _teamp.p, rfpct,
avg(_playerp.p / _teamp.p / rfpct) rf
--sum(_playerp.p) / sum(_teamp.p) / rfpct rfWeighted,
from _playerp join _teamp on _playerp.pug = _teamp.pug and _playerp.team = _teamp.team
              join _rfpct on _playerp.pug = _rfpct.pug and _playerp.team = _rfpct.team and _playerp.class = _rfpct.class
join players on _playerp.player = players.steamid
group by player
order by rf desc
--order by player
;
