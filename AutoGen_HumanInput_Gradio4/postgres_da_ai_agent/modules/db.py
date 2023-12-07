from datetime import datetime
import json
import sqlalchemy
from sqlalchemy import create_engine, text, MetaData, Table, select, inspect
from sqlalchemy.orm import sessionmaker

class SQLManager:
    def __init__(self):
        self.engine = None
        self.Session = None
        self.session = None
        self.metadata = MetaData()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            self.session.close()

    def connect_with_url(self, url):
        #try:
            self.engine = create_engine(url)
            self.Session = sessionmaker(bind=self.engine)
            self.session = self.Session()
            self.metadata.reflect(bind=self.engine)
        #except sqlalchemy.exc.InterfaceError as e:
        #    print("An error occurred while connecting to the database: ", str(e))

    #def upsert(self, table_name, _dict):
    #    metadata = MetaData(self.engine)
    #    table = Table(table_name, metadata, autoload_with=self.engine)
    #   # Check if the record exists
    #    query = select([table]).where(table.c.id == _dict['id'])
    #    existing_record = self.session.execute(query).fetchone()
    #    if existing_record:
            # Record exists, so update
    #        update_query = table.update().where(table.c.id == _dict['id']).values(**_dict)
    #        self.session.execute(update_query)
    #    else:
    #        # Record does not exist, so insert
    #       insert_query = table.insert().values(**_dict)
    #        self.session.execute(insert_query)
    #    self.session.commit()

    #def delete(self, table_name, _id):
        #delete_stmt = text(f"DELETE FROM {table_name} WHERE id = :id")
        #self.session.execute(delete_stmt, {'id': _id})
        #self.session.commit()

    def get(self, table_name, _id):
        select_stmt = text(f"SELECT * FROM {table_name} WHERE id = :id")
        result = self.session.execute(select_stmt, {'id': _id})
        return result.fetchone()

    def get_all(self, table_name):
        select_all_stmt = text(f"SELECT * FROM {table_name}")
        result = self.session.execute(select_all_stmt)
        return result.fetchall()

    # def run_sql(self, sql):
    #     self.cur.execute(sql)
    #     return self.cur.fetchall()

    def run_sql(self, sql) -> str:
        result = self.session.execute(text(sql))
        columns = result.keys()
        rows = result.fetchall()
        list_of_dicts = [dict(zip(columns, row)) for row in rows]

        json_result = json.dumps(list_of_dicts, indent=4, default=self.datetime_handler)
        return json_result

    def datetime_handler(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return str(obj)

    def get_table_definition(self, table_name):
        metadata = MetaData(bind=self.engine)
        table = metadata.tables[table_name]
        create_table_stmt = "CREATE TABLE {} (\n".format(table_name)

        for column in table.columns:
            create_table_stmt += "    {} {},\n".format(column.name, column.type)

        create_table_stmt = create_table_stmt.rstrip(",\n") + "\n);"
        return create_table_stmt

    def reflect_tables(self):
        self.metadata = MetaData()

        # Reflect tables for each schema
        for schema in ['dim', 'fact', 'dbo']:
            self.metadata.reflect(bind=self.engine, schema=schema)

    def get_all_table_names(self):
        table_names = []
        for schema in ['dim', 'fact', 'dbo']:
            inspector = inspect(self.engine)
            tables = inspector.get_table_names(schema=schema)
            # Prefix table name with schema
            table_names.extend([f"{schema}.{table}" for table in tables])
        return table_names

    def get_table_definitions_for_prompt(self):
        self.reflect_tables()
        table_names = self.get_all_table_names()
        definitions = []
        for table_name in table_names:
            try:
                # Access table with schema prefix
                table = self.metadata.tables[table_name]
                columns = ["{} {}".format(column.name, column.type) for column in table.columns]
                table_definition = "CREATE TABLE {} (\n  {});".format(table_name, ',\n  '.join(columns))
                definitions.append(table_definition)
            except KeyError:
                print("Error accessing " + table_name)
                continue
        return "\n\n".join(definitions)