# Failure cases (A3)

79 of 200 slice questions were answered incorrectly. Rule-based categories (see `eval/failures.py`):

| Category | Count |
|---|---|
| schema hallucination | 41 |
| wrong join | 11 |
| wrong aggregation | 6 |
| value mismatch | 5 |
| other | 16 |

## 10 examples

### #39 (concert_singer, medium) - schema hallucination

**Question:** what is the name and nation of the singer who have a song having 'Hey' in its name?

Gold: `SELECT name ,  country FROM singer WHERE song_name LIKE '%Hey%'`

Predicted: `SELECT T1.name ,  T1.country FROM singer AS T1 JOIN concert AS T2 ON T1.singer_id  =  T2.singer_id WHERE T2.song_name LIKE "%Hey%"`

Error: `OperationalError: no such column: T2.song_name`

### #94 (car_1, medium) - wrong join

**Question:** What is the full name of each car maker, along with its id and how many models it produces?

Gold: `SELECT T1.FullName ,  T1.Id ,  count(*) FROM CAR_MAKERS AS T1 JOIN MODEL_LIST AS T2 ON T1.Id  =  T2.Maker GROUP BY T1.Id;`

Predicted: `SELECT FullName, Id, COUNT(*) FROM car_makers GROUP BY FullName`

### #395 (course_teach, hard) - wrong aggregation

**Question:** List the most common hometown of teachers.

Gold: `SELECT Hometown FROM teacher GROUP BY Hometown ORDER BY COUNT(*) DESC LIMIT 1`

Predicted: `SELECT Hometown ,  count(*) FROM teacher GROUP BY Hometown ORDER BY count(*) DESC LIMIT 1`

### #417 (museum_visit, medium) - value mismatch

**Question:** What are the opening year and staff number of the museum named Plaza Museum?

Gold: `SELECT Num_of_Staff ,  Open_Year FROM museum WHERE name  =  'Plaza Museum'`

Predicted: `SELECT Open_Year ,  Num_of_Staff FROM museum WHERE Name  =  "Plaza Museum"`

### #110 (car_1, medium) - other

**Question:** What is the number of car models that are produced by each maker and what is the id and full name of each maker?

Gold: `SELECT Count(*) ,  T2.FullName ,  T2.id FROM MODEL_LIST AS T1 JOIN CAR_MAKERS AS T2 ON T1.Maker  =  T2.Id GROUP BY T2.id;`

Predicted: `SELECT count(*) ,  car_makers.id ,  car_makers.fullname FROM car_makers JOIN model_list ON car_makers.id  =  model_list.maker GROUP BY car_makers.id ,  car_makers.fullname`

### #40 (concert_singer, medium) - schema hallucination

**Question:** What is the name and country of origin of every singer who has a song with the word 'Hey' in its title?

Gold: `SELECT name ,  country FROM singer WHERE song_name LIKE '%Hey%'`

Predicted: `SELECT T1.name ,  T1.country FROM singer AS T1 JOIN concert AS T2 ON T1.singer_id  =  T2.singer_id JOIN song AS T3 ON T2.concert_id  =  T3.concert_id WHERE T3.song_name LIKE "%Hey%"`

Error: `OperationalError: no such table: song`

### #105 (car_1, hard) - wrong join

**Question:** How many car makers are there in each continents? List the continent name and the count.

Gold: `SELECT T1.Continent ,  count(*) FROM CONTINENTS AS T1 JOIN COUNTRIES AS T2 ON T1.ContId  =  T2.continent JOIN car_makers AS T3 ON T2.CountryId  =  T3.Country GROUP BY T1.Continent;`

Predicted: `SELECT continents.Continent ,  COUNT(car_makers.Id) FROM continents JOIN car_makers ON continents.ContId = car_makers.Country GROUP BY continents.Continent`

### #472 (wta_1, medium) - wrong aggregation

**Question:** What are the first names of all players, and their total ranking points?

Gold: `SELECT sum(ranking_points) ,  T1.first_name FROM players AS T1 JOIN rankings AS T2 ON T1.player_id  =  T2.player_id GROUP BY T1.first_name`

Predicted: `SELECT p.first_name, SUM(r.ranking_points) FROM players p JOIN rankings r ON p.player_id = r.player_id GROUP BY p.first_name HAVING COUNT(*) = 1`

### #730 (world_1, medium) - value mismatch

**Question:** What is the average GNP and total population in all nations whose government is US territory?

Gold: `SELECT avg(GNP) ,  sum(population) FROM country WHERE GovernmentForm  =  "US Territory"`

Predicted: `SELECT AVG(GNP), SUM(Population) FROM country WHERE GovernmentForm = 'Nonmetropolitan Territory of the United States'`

### #153 (car_1, easy) - other

**Question:** In which years cars were produced weighing no less than 3000 and no more than 4000 ?

Gold: `select distinct year from cars_data where weight between 3000 and 4000;`

Predicted: `SELECT YEAR FROM cars_data WHERE Weight  >=  3000 AND Weight  <=  4000`
