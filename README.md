# NLP-DISCOGRAFY

Um projeto de scraping e análise da discografia dos Engenheiros do Hawaii, coletando dados de múltiplas fontes para criar um dataset completo com álbuns, faixas e letras.

## 📋 Sobre o Projeto

Este projeto realiza o scraping da discografia completa da banda Engenheiros do Hawaii, utilizando diferentes fontes de dados:
- **Wikipedia**: Para informações de álbuns e tracklists
- **Genius**: Para letras completas das músicas

Os dados são exportados em formato JSON e CSV, permitindo análises posteriores de processamento de linguagem natural (NLP) sobre as letras da banda.

## 🚀 Funcionalidades

- **Scraping Multi-fonte**: Coleta dados da Wikipedia e API do Genius
- **Exportação Flexível**: Gera arquivos JSON e CSV separados por álbum
- **Tratamento de Duplicatas**: Evita duplicação de faixas entre diferentes fontes
- **Normalização de Dados**: Padroniza títulos e informações
- **Rate Limiting**: Controle de requisições para APIs
- **Logs Detalhados**: Acompanhamento do progresso via tqdm e logging

## 📦 Instalação

1. **Clone o repositório**:
```bash
git clone https://github.com/seu-usuario/NLP-DISCOGRAFY.git
cd NLP-DISCOGRAFY
```

2. **Instale as dependências**:
```bash
pip install -r requirements.txt
```

3. **Configure as variáveis de ambiente** (opcional):
Crie um arquivo `.env` na raiz do projeto:
```env
GENIUS_ACCESS_TOKEN=seu_token_genius_aqui
```

## 💻 Uso

### Script Principal (Multi-fonte)

```bash
python scrape_engenheiros.py [opções]
```

**Opções principais**:
- `--include-lyrics`: Ativa busca de letras
- `--lyrics-source genius`: Usa apenas o Genius como fonte de letras
- `--source wikipedia`: Define fonte de dados (padrão: wikipedia)
- `--out data/resultado.json`: Arquivo de saída JSON
- `--csv-dir data/csvs/`: Diretório para CSVs por álbum
- `--verbose`: Logs detalhados

**Exemplos**:
```bash
# Scraping básico apenas com dados estruturais
python scrape_engenheiros.py

# Incluindo letras do Genius
python scrape_engenheiros.py --include-lyrics --lyrics-source genius

# Saída personalizada
python scrape_engenheiros.py --out meus_dados.json --csv-dir meus_csvs/
```

### Script Genius Only

Para usar exclusivamente a API do Genius:

```bash
python scrape_genius_only.py [opções]
```

**Opções**:
- `--out data/engenheiros_genius.json`: Arquivo de saída
- `--csv-dir data/albuns_genius_csv/`: Diretório para CSVs
- `--max-songs 500`: Limite de músicas
- `--verbose`: Logs detalhados

## 📂 Estrutura do Projeto

```
NLP-DISCOGRAFY/
├── scraper/                    # Módulo principal
│   ├── __init__.py
│   ├── crawler.py              # Cliente HTTP
│   ├── discography_scraper.py  # Scraper Wikipedia
│   └── genius_provider.py      # Interface Genius API
├── data/                       # Dados coletados
│   ├── albuns_genius_separados_csv/  # CSVs por álbum
│   └── engenheiros_genius_albums.json  # Dados completos
├── scrape_engenheiros.py       # Script principal
├── scrape_genius_only.py       # Script apenas Genius
├── requirements.txt            # Dependências
└── README.md                   # Este arquivo
```

## 📊 Formato dos Dados

### JSON Principal
```json
[
  {
    "album_title": "Nome do Álbum",
    "album_url": "URL_fonte",
    "release_year": 1985,
    "tracks": [
      {
        "track_number": 1,
        "title": "Nome da Música",
        "lyrics": "Letra completa da música..."
      }
    ]
  }
]
```

### CSV por Álbum
Cada álbum gera um arquivo CSV com colunas:
- `track_number`: Número da faixa
- `title`: Título da música
- `lyrics`: Letra completa

## 🛠️ Dependências

- **requests** (≥2.32.0): Requisições HTTP
- **beautifulsoup4** (≥4.12.3): Parsing HTML
- **tqdm** (≥4.66.4): Barras de progresso
- **python-dotenv** (≥1.0.1): Variáveis de ambiente

## 🔧 Configuração Avançada

### Token do Genius
Para usar a API do Genius, você precisa:
1. Criar uma conta em [genius.com](https://genius.com/developers)
2. Criar uma aplicação e obter o Access Token
3. Definir a variável `GENIUS_ACCESS_TOKEN` no arquivo `.env`

### Personalização
O projeto suporta diferentes estratégias de coleta:
- **Prefer API**: Prioriza dados de APIs sobre scraping web
- **Prefer Genius**: Prioriza letras do Genius sobre outras fontes
- **Fallback Strategy**: Define ordem de prioridade entre fontes

## 📈 Dados Coletados

Atualmente o projeto coletou:
- **13 álbuns** dos Engenheiros do Hawaii
- **Centenas de faixas** com letras completas
- **Versões acústicas e ao vivo** incluídas
- **Metadados** como ano de lançamento e URLs

## 🤝 Contribuição

Contribuições são bem-vindas! Para contribuir:

1. Faça um fork do projeto
2. Crie uma branch para sua feature (`git checkout -b feature/AmazingFeature`)
3. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
4. Push para a branch (`git push origin feature/AmazingFeature`)
5. Abra um Pull Request

## 📝 Licença

Este projeto está licenciado sob a [MIT License](LICENSE).

## ⚖️ Considerações Legais

Este projeto é destinado exclusivamente para fins educacionais e de pesquisa. As letras e informações coletadas permanecem propriedade de seus respectivos detentores de direitos autorais.

## 🎵 Sobre os Engenheiros do Hawaii

Os Engenheiros do Hawaii foram uma banda brasileira de rock formada em 1985 em Porto Alegre. Liderada por Humberto Gessinger, a banda se tornou uma das mais influentes do rock nacional, com letras que misturam crítica social, filosofia e poesia.

---

**Desenvolvido com ❤️ para preservar e analisar a rica discografia dos Engenheiros do Hawaii**