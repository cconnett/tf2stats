create  table if not exists pp as select * from pugplayers;
create index if not exists p4 on pp (pug, player);
create index if not exists p3 on pp (player);
create index if not exists pc on pp (player, class);

create  table if not exists p as select * from pugs;
create index if not exists p1 on p (id);

create  table if not exists _summary as
select r.pug pug, pp.team team, e.srcplayer player,
pp.class class, e.type type, vicpp.class vicclass,
count(*) n, pp.totaltime/60.0 m,
(strftime('%s', p.end) - strftime('%s', p.begin))/60.0 matchtime
from events e join rounds r on e.round = r.id
join pp on r.pug = pp.pug and e.srcplayer = pp.player
join p on pp.pug = p.id
left outer join pp vicpp on r.pug = vicpp.pug and e.vicplayer = vicpp.player
where r.type = 'normal' and e.type in (5, 6, 9)
group by r.pug, e.srcplayer, pp.class, e.type, vicpp.class
order by r.pug, pp.team, e.srcplayer, e.type, vicpp.class;
create index if not exists _summary_pptcv on _summary (pug, player, type, class, vicclass);
create index if not exists _summary_ptcv on _summary (player, type, class, vicclass);
create index if not exists _summary_tcpp on _summary (type, class, pug, player);
create index if not exists _summary_tcpt on _summary (type, class, pug, team);

create  table if not exists _deaths as
select r.pug pug, pp.team team, e.vicplayer player,
pp.class class, srcpp.class srcclass,
count(*) n, pp.totaltime/60.0 m,
(strftime('%s', p.end) - strftime('%s', p.begin))/60.0 matchtime
from events e join rounds r on e.round = r.id
join pp on r.pug = pp.pug and e.vicplayer = pp.player
join p on pp.pug = p.id
left outer join pp srcpp on r.pug = srcpp.pug and e.srcplayer = srcpp.player
where r.type = 'normal' and e.type = 5
group by r.pug, e.vicplayer, pp.class, srcpp.class
order by r.pug, pp.team, e.srcplayer, srcpp.class;
create index if not exists _deaths_ppcts on _deaths (pug, player, class, srcclass);
create index if not exists _deaths_pcts on _deaths (player, class, srcclass);

--Range factor setup
--Overall stats for all matches
create  table if not exists _classtime as
select class, sum(totaltime) classtime
from pp
where class != 'medic'
group by class;

create  table if not exists _classtime_factor as
select class, (select max(cast(classtime as float)) from _classtime) / classtime cf
from _classtime;

create  table if not exists _rfk as
select class class, sum(n) n
from _summary
where type = 5 and class != 'medic'
group by class;

create  table if not exists _rfa as
select class, sum(n) n
from _summary
where type = 6 and class != 'medic'
group by class;

create  table if not exists _rfc as
select class, sum(n) n
from _summary
where type = 9 and class != 'medic'
group by class;

create  table if not exists _rfp as
select k.class, k.n + 0.5 * a.n + 2.0 * c.n p
from _rfk k join _rfa a on k.class = a.class
            join _rfc c on k.class = c.class;

create  table if not exists _rfbase as
select _cf.class class, p * cf rfbase
from _classtime_factor _cf join _rfp on _cf.class = _rfp.class;

create  table if not exists _rfpct as
select pp.pug pug, pp.team team, pp.class class, rfbase,
       rfbase / (select sum(rfbase) from pp thisPP join _rfbase on thisPP.class = _rfbase.class
                  where thisPP.pug = pp.pug and thisPP.team = pp.team) rfpct
from pp join _rfbase on pp.class = _rfbase.class
where pp.class != 'medic'
group by pp.pug, pp.team, pp.class;
create index if not exists rfpct_ptc on _rfpct (pug, team, class);

--select * from _rfpct;

--Individual player stats (by pug and player)
create  table if not exists _playerk as
select pug, player, class, sum(n) n
from _summary
where type = 5 and class != 'medic'
group by pug, player;
create index if not exists pkpp on _playerk (pug, player);

create  table if not exists _playera as
select pug, player, class, sum(n) n
from _summary
where type = 6 and class != 'medic'
group by pug, player;
create index if not exists papp on _playera (pug, player);

create  table if not exists _playerc as
select pug, player, class, sum(n) n
from _summary
where type = 9 and class != 'medic'
group by pug, player;
create index if not exists pcpp on _playerc (pug, player);
--select * from pp where pug = 1 order by team;

create  table if not exists _playerp as
select pp.pug pug, pp.team team, pp.player player, pp.class class,
       coalesce((k.n + 0.5 * a.n + 2.0 * c.n), 0)
       * max((select strftime('%s', pugs.end) - strftime('%s', pugs.begin)
                from p pugs where pugs.id = k.pug)
             / cast(totaltime as float), 1) p,
       max((select strftime('%s', pugs.end) - strftime('%s', pugs.begin)
              from p pugs where pugs.id = k.pug)
           / cast(totaltime as float), 1) adjustment
from pp left outer join _playerk k on pp.pug = k.pug and pp.player = k.player
        left outer join _playera a on pp.pug = a.pug and pp.player = a.player
        left outer join _playerc c on pp.pug = c.pug and pp.player = c.player
where pp.player in (select thisPP.player from pp thisPP
                    where thisPP.pug = pp.pug
                    group by thisPP.pug, thisPP.player
                    order by sum(totaltime) desc
                    limit 12)
  and pp.class != 'medic';

--select * from _playerp order by pug, team;--where pug = 84;
--select player, class from pp

--Team frag counts (by pug and team)
create  table if not exists _teamk as
select pug, team, sum(n) n
from _summary
where type = 5 and class != 'medic'
group by pug, team;
create index if not exists tkpt on _teamk (pug, team);

create  table if not exists _teama as
select pug, team, sum(n) n
from _summary
where type = 6 and class != 'medic'
group by pug, team;
create index if not exists tapt on _teama (pug, team);

create  table if not exists _teamc as
select pug, team, sum(n) n
from _summary
where type = 9 and class != 'medic'
group by pug, team;
create index if not exists tcpt on _teamc (pug, team);

create  table if not exists _teamp as
select k.pug pug, k.team team, k.n + 0.5 * a.n + 2.0 * c.n p
from _teamk k join _teama a on k.pug = a.pug and k.team = a.team
              join _teamc c on k.pug = c.pug and k.team = c.team;

--select * from _teamp;
create  table if not exists _rf_inpug as
select _playerp.player player, _playerp.pug pug, _playerp.team team,
       _playerp.p / _teamp.p / rfpct rf
from _playerp join _teamp on _playerp.pug = _teamp.pug and _playerp.team = _teamp.team
              join _rfpct on _playerp.pug = _rfpct.pug and _playerp.team = _rfpct.team and _playerp.class = _rfpct.class
              join players on _playerp.player = players.steamid
group by player, pug;
create index if not exists _rf_inpug_pp on _rf_inpug (player, pug);
--select * from _rf_inpug;

create  table if not exists _rf as
select player, pug, team,
       (select avg(rf) from _rf_inpug innerRF
         where innerRF.player = outerRF.player
           and innerRF.pug != outerRF.pug) rf
from _rf_inpug outerRF
group by player, pug;
create index if not exists _rf_pp on _rf (player, pug);
--select * from _rf;

create  table if not exists _teamrf as
select pug, team, sum(coalesce(rf,1.0)) rf
from _rf
group by pug, team;
--select * from _teamrf;
--End range factor setup.

-- Table of bonus rounds (extra phantom rounds added to pugs that go
-- less than 9 rounds, to reward the model for being confident of
-- lop-sided matches)
drop table if exists _bonus_rounds;
create table if not exists _bonus_rounds as
select random() id, map, 'bonus' type, winner, begin, end, 'bonus' endreason, p.id pug from p where 1 <= 9 - redscore - bluescore
union all
select random() id, map, 'bonus' type, winner, begin, end, 'bonus' endreason, p.id pug from p where 2 <= 9 - redscore - bluescore
union all
select random() id, map, 'bonus' type, winner, begin, end, 'bonus' endreason, p.id pug from p where 3 <= 9 - redscore - bluescore
union all
select random() id, map, 'bonus' type, winner, begin, end, 'bonus' endreason, p.id pug from p where 4 <= 9 - redscore - bluescore
order by pug;
