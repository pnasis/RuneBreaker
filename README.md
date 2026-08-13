# Rune Decryptor corpus builder

This folder contains a helper that creates the language-model `.txt` files
used by `runebreaker.py`.

## Build all 10 corpora

```bash
python build_corpora.py
```

It creates:

```text
corpora/
    de.txt
    en.txt
    es.txt
    fr.txt
    grc.txt
    it.txt
    la.txt
    nl.txt
    ru.txt
    sv.txt
```

The default build selects up to 12 public-domain Project Gutenberg books per
language (with different authors where possible), strips Gutenberg boilerplate,
and takes up to 750,000 characters from each book. Ancient Greek is built from
original Greek PerseusDL TEI texts instead of Modern Greek translations.

## Smaller/faster build

```bash
python build_corpora.py --books 5 --chars-per-book 300000
```

## Build only selected languages

```bash
python build_corpora.py --languages en de nl sv
```

## Larger corpus

```bash
python build_corpora.py --books 20 --chars-per-book 1000000
```

Then solve:

```bash
python runebreaker.py solve cipher.txt --corpora corpora --restarts 50 --steps 60000
```

_**NOTE: Internet access is required while `build_corpora.py` is running!**_
