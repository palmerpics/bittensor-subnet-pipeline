.PHONY: ingest ingest-hourly transform transform-dev alerts alerts-dev dash

ingest:            ## daily sweep -> R2 bronze
	python -m ingest.run_ingest --cadence daily

ingest-hourly:     ## pools only -> R2 bronze
	python -m ingest.run_ingest --cadence hourly

transform:         ## dbt against R2 (prod)
	cd transform && DBT_PROFILES_DIR=. dbt build

transform-dev:     ## dbt against local fixtures
	cd transform && mkdir -p target/gold && \
	DBT_PROFILES_DIR=. BRONZE_ROOT=../fixtures/bronze dbt build --target dev

alerts:            ## alert rules against R2 gold
	python -m alerts.check_alerts

alerts-dev:        ## alert rules against local gold
	GOLD_ROOT=transform/target/gold python -m alerts.check_alerts

dash:              ## local Evidence dev server (needs parquet in sources/subnets/data)
	cd dashboard && npm install --legacy-peer-deps && npm run sources && npm run dev
