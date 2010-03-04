.output wpSummary.sql
.mode insert wpSummary
select "map","point","o1","o2","o4","o7","oc","d1","d2","d4","d7","dc",
sum((case when midowner is null then 'Blue' else midowner end) = fight_winner) as fightsWon, 
sum((case when midowner is null then 'Blue' else midowner end) = round_winner) as roundsWon, 
count(*) as sampleSize
from stats
where 
--midowner is not null and 
round_winner is not null and fight_winner is not null
group by 
"map",
"point"
,"o1"
,"o2"
,"o4"
,"o7"
,"oc"
,"d1"
,"d2"
,"d4"
,"d7"
,"dc";
--having sampleSize >= 30
--order by sampleSize desc
