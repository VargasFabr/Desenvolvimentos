# Detecção de doença em trigo por imagem (drone → CNN)

Classificar folha/planta em ferrugem das folhas, ferrugem do tronco ou saudável — triagem visual em escala a partir de fotos, com modelo transferido do ImageNet.

## Problema de negócio

Ferrugem reduz produtividade e exige resposta rápida de manejo. Inspeção 100% humana não cobre talhão. O agrônomo precisa de um **primeiro filtro** confiável por foto (estilo drone/campo) antes de deslocar equipe. Falso negativo atrasa tratamento; falso positivo gera custo de aplicação.

## Pergunta que o projeto responde

Com InceptionV3 (ImageNet, fine-tune das últimas camadas) e holdout 20% das imagens rotuladas, qual a acurácia e o desempenho por classe?

## Abordagem (do dado à decisão)

1. Ler `dados/treino` (OpenCV → 224×224, normalização).
2. Codificar labels (`LabelBinarizer` → `modelos/binarizador_dsa.pickle`); split 80/20.
3. InceptionV3 sem topo + pooling + softmax; congelar o miolo e treinar o topo / últimas ~50 camadas (BN tratada à parte).
4. Adam, early stopping e checkpoint por `val_loss`.
5. Avaliar holdout; demo em imagem de `dados/teste` (sem rótulo no fluxo de demo).

## Decisões de desenho

- **Transfer learning parcial** — amostra limitada; treinar tudo do zero overfitting cedo.
- **Holdout do treino rotulado** como métrica oficial; pasta `teste` é demonstração operacional.
- Mixed precision se houver GPU; em Windows nativo com TF recente a GPU pode não estar disponível — o notebook registra isso.

## Entrega e resultado

| Artefato | Uso |
|----------|-----|
| `modelos/modelo_dsa.keras` | Rede treinada |
| `modelos/binarizador_dsa.pickle` | Mapeamento classe ↔ label |
| `dados/treino/`, `dados/teste/` | Imagens |

No notebook revisado: **562** imagens; holdout **113**; acurácia holdout **0,805**. Por classe (aproximado do report): tronco forte (F1 ~0,86); folhas intermediário; **saudável fraco** (poucos exemplos no holdout, n=5).

Leitura de negócio: útil como triagem para ferrugens; classe saudável exige mais dados antes de automatizar “liberar talhão”.

## Estrutura do repositório

| Arquivo | Papel |
|---------|--------|
| `doenca_planta.ipynb` | Fluxo canônico |
| `Projeto11.ipynb` | Versão original |
| `dados/`, `modelos/` | Dados e artefatos |
| `requirements.txt`, `LEIAME.txt` | Ambiente |

Referência interna DSA: Projeto 11.

## Como executar

1. Ambiente em `LEIAME.txt` + deps (TensorFlow, OpenCV, imutils, scikit-learn).
2. Executar `doenca_planta.ipynb`. A primeira vez baixa pesos ImageNet.
3. Confirme GPU/CPU conforme o log do TensorFlow na sua máquina.

## Limitações e próximos passos

- Classe saudável sub-representada no holdout — métrica global mascara isso.
- Risco de overfitting (acurácia de treino alta).
- Próximo passo: mais imagens saudáveis, augmentação controlada e validação em campo com rótulo agronômico.
