# Cliente para conexão com o banco de dados e as vies disponívels na conexão SQL

import pyodbc

driver = pyodbc.drivers()
#print("Drivers disponíveis:", driver)

class SQLClient:
    def __init__(self, server: str, database: str, username: str, password: str):
        self.server = server
        self.database = database
        self.username = username
        self.password = password
        self.connection = None

    def connect(self):
        try:
            self.connection = pyodbc.connect(
                f'DRIVER={driver[0]};SERVER={self.server};DATABASE={self.database};UID={self.username};PWD={self.password}'
            )
        except Exception as e:
            print(f"Erro ao conectar ao banco de dados: {e}")

    def disconnect(self):
        if self.connection:
            self.connection.close()

    def execute_query(self, query: str, params=None):
        """
        Executa a consulta SQL fornecida e retorna os resultados. 
        Certifique-se de que a conexão esteja estabelecida antes de chamar este método.
        
        Args:
            query (str): A consulta SQL com placeholders ? para parâmetros
            params (tuple/list, optional): Parâmetros para substituir os placeholders ?
        
        Returns:
            list: Lista de dicionários, onde cada dicionário representa uma linha do resultado, 
                  com as chaves correspondendo aos nomes das colunas.
        """
        if not self.connection:
            print("Conexão não estabelecida. Por favor, conecte-se primeiro.")
            return None
        
        try:
            cursor = self.connection.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            columns = [column[0] for column in cursor.description]
            results = [dict(zip(columns, row)) for row in cursor.fetchall()]
            return results
        except Exception as e:
            print(f"Erro ao executar a consulta: {e}")
            return None
        

if __name__ == "__main__":
    # Exemplo de uso do SQLClient
    env_path = r"C:\Users\pedroruppenthal\Documents\.env"
    import os
    from dotenv import load_dotenv

    import pyodbc
    print(pyodbc.drivers())

    load_dotenv(env_path)    

    username = os.getenv("SQL_USER", "")
    password = os.getenv("SQL_PASS", "")

    print(f"Usuário: {username}"
          f"\nSenha: {'*' * len(password) if password else 'Não encontrada'}"
          )
    
    client = SQLClient(
        server=os.getenv("SQL_SERVER", ""),
        database=os.getenv("SQL_DATABASE", ""),
        username=username,
        password=password
    )
    client.connect()

    if client.connection:
        print(client.connection.getinfo(pyodbc.SQL_SERVER_NAME))
    
    query = "SELECT * FROM dbo.Empresas_GC"
    results = client.execute_query(query)
    if results is None:
        raise Exception("Falha ao executar a consulta SQL.")
    print(results)
    
    # if results:
    #     print(results)
    
    client.disconnect()

    # Procura item com coluna "DIM_Cadastro_Unico_Hist[cdEmpreendimento]" igual a 6190
    item = next((row for row in results if row.get("DIM_Cadastro_Unico_Hist[cdEmpreendimento]") == 6190), None)
    if item:
        print("Item encontrado:", item)
        print(item.keys())