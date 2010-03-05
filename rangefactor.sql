create temporary table if not exists pp as select * from pugplayers;
create index p4 on pp (pug, player);
create index p3 on pp (player);
create index pt on pp (pug, team);

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
where e.type = 5 and pp.class != 'medic'
group by pp.class;

create temporary table _assists as
select pp.class class, count(*) n
from events e join rounds r on e.round = r.id join pp on e.srcplayer = pp.player and r.pug = pp.pug
where e.type = 6 and pp.class != 'medic'
group by pp.class;

create temporary table _p as
select k.class, k.n + 0.5 * a.n p
from _kills k join _assists a on k.class = a.class;

create temporary table _rfbase as
select _cf.class class, p * cf rfbase
from _classtime_factor _cf join _p on _cf.class = _p.class;

create temporary table _rfpct as
select pp.pug, pp.team, pp.class, rfbase,
       rfbase / (select sum(rfbase) from pp thisPP join _rfbase on thisPP.class = _rfbase.class
                  where thisPP.pug = pp.pug and thisPP.team = pp.team) rfpct
from pp join _rfbase on pp.class = _rfbase.class
where pp.class != 'medic'
group by pp.pug, pp.team, pp.class;

select * from _rfpct;
