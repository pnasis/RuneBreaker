# RuneBreaker

**Experimental multilingual cryptanalysis tool for monoalphabetic substitution ciphers using statistical language models and heuristic search.**

RuneBreaker is a Python-based tool for analyzing and automatically solving **monoalphabetic substitution ciphers**. It combines character-level statistical language models with heuristic key search to estimate plaintext and recover substitution mappings.

The project supports **10 languages**: English, German, Spanish, French, Italian, Latin, Dutch, Russian, Swedish and Ancient Greek.

## Features

* **Multilingual cryptanalysis** across 10 supported languages
* **Character n-gram language models** using trigram and quadgram statistics
* **Heuristic key search** using simulated annealing
* **Multiple randomized restarts** to explore the substitution-key search space
* **Automatic language comparison** when the plaintext language is unknown
* **Ciphertext analysis** including symbol frequencies, word frequencies, and word patterns
* **Known-plaintext constraints** through fixed symbol mappings
* **Local search around an existing mapping** for correcting near-solution keys
* **Mapping export** for preserving recovered substitution keys
* Reproducible corpus generation from public-domain literary texts

## How It Works

For a given ciphertext, RuneBreaker searches for a substitution mapping that produces plaintext with a high statistical likelihood under a language model.

The solver follows a heuristic optimization process:

1. Analyze the ciphertext and identify its symbols and word structure.
2. Initialize a substitution mapping using character-frequency information.
3. Construct a language model from a corpus for each candidate language.
4. Randomly perturb the substitution mapping.
5. Evaluate the resulting plaintext using a statistical scoring function.
6. Accept or reject candidate mappings using **simulated annealing**.
7. Repeat the optimization from multiple randomized starting points.
8. Rank the resulting solutions according to their language-model scores.

The scoring model combines:

* character-level **trigram frequencies**
* character-level **quadgram frequencies**
* common-word information
* corpus-derived word frequencies
* penalties for implausible one-letter words

This approach allows the solver to recover plaintext without requiring a predefined dictionary or manually specified substitution key.

## Supported Languages

| Code  | Language      |
| ----- | ------------- |
| `de`  | German        |
| `en`  | English       |
| `es`  | Spanish       |
| `fr`  | French        |
| `grc` | Ancient Greek |
| `it`  | Italian       |
| `la`  | Latin         |
| `nl`  | Dutch         |
| `ru`  | Russian       |
| `sv`  | Swedish       |

Ancient Greek is handled separately from the modern-language corpora and uses original Greek texts from the Perseus Digital Library ecosystem.

## Installation

RuneBreaker requires **Python 3** and uses only the Python standard library.

Clone the repository:

```bash
git clone https://github.com/pnasis/RuneBreaker.git
cd RuneBreaker
```

No third-party Python packages are required.

## Building the Language Corpora

RuneBreaker uses language-specific text corpora to construct its statistical models.

The included corpus builder retrieves public-domain texts and constructs corpora for the supported languages.

Build the default corpora:

```bash
python build_corpora.py
```

The resulting directory contains:

```text
corpora/
├── de.txt
├── en.txt
├── es.txt
├── fr.txt
├── grc.txt
├── it.txt
├── la.txt
├── nl.txt
├── ru.txt
└── sv.txt
```

The default configuration selects up to 12 public-domain books per language and limits the amount of text extracted from each book.

### Smaller / faster corpus

For a faster test run:

```bash
python build_corpora.py --books 5 --chars-per-book 300000
```

### Selected languages

Build only specific language models:

```bash
python build_corpora.py --languages en de nl sv
```

### Larger corpus

For a larger language model:

```bash
python build_corpora.py --books 20 --chars-per-book 1000000
```

> **Note:** Internet access is required while building the corpora because source texts and metadata are retrieved from external repositories.

## Usage

### Analyze a ciphertext

Before attempting to solve a ciphertext, inspect its structure:

```bash
python runebreaker.py analyze cipher.txt
```

This reports:

* number of distinct ciphertext symbols;
* number of word tokens;
* number of unique words;
* symbol frequencies;
* common ciphertext words;
* word lengths and structural patterns; and
* one-letter words.

### Solve a ciphertext

To automatically evaluate all supported languages:

```bash
python runebreaker.py solve cipher.txt --corpora corpora
```

RuneBreaker ranks the candidate solutions according to their statistical scores.

### Specify a language

If the plaintext language is known:

```bash
python runebreaker.py solve cipher.txt \
    --language en \
    --corpora corpora
```

### Increase the search effort

The solver supports configurable numbers of restarts and optimization steps:

```bash
python runebreaker.py solve cipher.txt \
    --corpora corpora \
    --restarts 50 \
    --steps 60000
```

More restarts and optimization steps generally increase the search effort at the cost of additional computation.

### Reproducible runs

A random seed can be supplied:

```bash
python runebreaker.py solve cipher.txt \
    --corpora corpora \
    --seed 42
```

### Save a recovered mapping

The best solution can be exported:

```bash
python runebreaker.py solve cipher.txt \
    --corpora corpora \
    --save mapping.json
```

### Fix known mappings

Known ciphertext-to-plaintext mappings can be supplied as constraints:

```bash
python runebreaker.py solve cipher.txt \
    --corpora corpora \
    --fix A=e \
    --fix B=t
```

### Explore nearby solutions

If an approximate mapping is already available, RuneBreaker can search nearby mappings:

```bash
python runebreaker.py nearby cipher.txt mapping.json \
    --corpora corpora
```

The `nearby` command evaluates mappings generated by swapping one or two pairs of substitutions and ranks the resulting plaintext candidates.

## Corpus Construction

The corpus builder uses:

* **Project Gutenberg** texts for German, English, Spanish, French, Italian, Latin, Dutch, Russian, and Swedish;
* **Perseus Digital Library / canonical-greekLit** sources for Ancient Greek.

The corpus construction process attempts to improve diversity by selecting texts from different authors and excludes obvious non-prose material such as dictionaries, catalogues, bibliographies, and similar sources where possible.

The resulting corpora are intended as **practical statistical models for cryptanalysis**, rather than linguistically comprehensive representations of each language.

## Project Structure

```text
RuneBreaker/
├── build_corpora.py     # Language-corpus construction
├── runebreaker.py       # Cryptanalysis and solving engine
├── README.md
└── LICENSE
```

## Limitations

RuneBreaker is designed primarily for **monoalphabetic substitution ciphers** and makes several simplifying assumptions.

Performance can depend substantially on:

* ciphertext length
* plaintext language
* corpus quality and representativeness
* vocabulary and writing style
* search parameters
* the structure of the underlying substitution cipher

Short ciphertexts and texts with unusual vocabulary can be particularly difficult to solve reliably.

The statistical models should therefore be treated as heuristic scoring mechanisms rather than definitive measures of plaintext correctness.

## Motivation

The project explores the application of **statistical language modelling and heuristic optimization to classical cryptanalysis**.

Beyond implementing a cipher solver, RuneBreaker provides an experimental environment for investigating how corpus composition, language-specific statistics and search parameters influence automated plaintext recovery.

## License

This project is released under the **MIT License**.
