import os
import requests
import json
import psycopg2
import sqlalchemy as sa
import pandas as pd


def execute_rds_query(db_identifier, query, params=None):
    """
    Executes a SELECT query on the specified RDS database and returns the results.
    
    Args:
        db_indentifier (str): The identifier of the RDS database.
        query (str): The SQL SELECT query to execute.
        params (tuple, optional): Parameters to pass to the SQL query.
    """

    # db_idenfitier='postgresql+psycopg2://username:password@host:port/database'
    print(f"Executing query on RDS: {db_identifier}")
    if db_identifier is None:
        db_identifier = os.environ.get("DB_IDENTIFIER")

    if query is None:
        query = os.environ.get("DB_QUERY")

    url = db_identifier

    conn = None
    ret = None
    try : 
        conn = sa.create_engine(url, client_encoding='utf8', connect_args={'options': '-csearch_path={}'.format('braindb')}).raw_connection()
        ret = pd.read_sql(query, conn, params=params)
    except Exception as e:
        print(f"Error executing query: {e}")
        ret = None
    finally:
        if conn is not None:
            conn.close()    

    return ret



