import datetime as dt
import time
from airflow.operators.s3_key_sensor_plugin import S3KeySensor
from airflow.operators.redshift_load_plugin import S3ToRedshiftOperator
from airflow.operators.s3_key_rename_plugin import S3KeyRenameOperator
from airflow.operators.looker_schedule_run_plugin import LookerScheduleRunOperator

from airflow import DAG

default_args = {
    'owner': 'Jesse Carah',
    'start_date': dt.datetime(2018, 11, 20),
    'retries': 2,
    'retry_delay': dt.timedelta(minutes=5)
}

dag = DAG('i__looker-to-redshift',
    default_args=default_args,
    schedule_interval='@once'
)



# tables = [ 'history', 'look','node', 'user_facts'
# , 'merge_query', 'query', 'source_query', 'user', 'merge_query_source_query',
# 'result_maker','sql_runner_query']
tables = ['user']

for table in tables:
    build_schedule = LookerScheduleRunOperator(
        task_id='{0}_schedule_build'.format(table),
        looker_conn_id='looker_api',
        table=table,
        dag=dag
        )

    sense_s3_key =  S3KeySensor(
        task_id='{0}_sense'.format(table),
        verify=False,
        wildcard_match=True,
        aws_conn_id='s3',
        bucket_name='jessecarah', # refactor to use meta data from connection
        bucket_key='{0}/{0}_{1}*'.format(table, time.strftime('%Y-%m-%d')),
        timeout=18*60*60,
        poke_interval=30,
        dag=dag
        )

    rename = S3KeyRenameOperator(
        task_id='{0}_rename'.format(table),
        s3_conn_id='s3',
        s3_bucket='jessecarah', # refactor to use meta data from connection
        table=table,
        dag=dag
        )

    load = S3ToRedshiftOperator(
        task_id='{0}_load'.format(table),
        s3_conn_id='s3',
        s3_bucket='jessecarah',
        s3_key='{0}/{0}.csv'.format(table),
        load_type='rebuild',
        redshift_conn_id='redshift',
        redshift_schema='airflow',
        table=table,
        copy_params=["COMPUPDATE OFF",
                      "STATUPDATE OFF",
                      "FORMAT as CSV",
                      "TIMEFORMAT 'auto'",
                      "TRUNCATECOLUMNS",
                      "region as 'us-east-1'",
                      "IGNOREHEADER 1"],
        origin_schema='../templates/{0}_schema.json'.format(table),
        schema_location='local',
        dag=dag
        )

    build_schedule >> sense_s3_key >> rename >> load
    
