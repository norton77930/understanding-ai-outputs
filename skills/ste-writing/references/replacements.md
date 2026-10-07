# Replacement list (strict strictness)

This list names words and phrases to avoid in strict STE, and a plain choice for each. The checker `scripts/ste_check.py` reads the first column and reports every match.

## Source and license

- The seed is the US Federal Plain Language Guidelines (plainlanguage.gov). Federal employees wrote them as part of their official work. Works of US federal employees are in the public domain under 17 U.S.C. section 105, so we can use them freely.
- We took only the idea of each substitution, plus common wordy phrases from general experience. We wrote every entry and every note ourselves in our own words.
- This is not the ASD-STE100 dictionary. It does not copy it, and it is not derived from it. See `docs/adr/0001` in the repository.

## How the checker uses it

- The first column is the term. The checker matches it as whole words, without regard to case.
- A single-word term also matches its simple inflections. "utilize" also catches "utilizes", "utilized" and "utilizing".
- A multi-word term matches as written.
- The list leaves out words that are also the normal technical term in some contexts (for example "execute" for running code). Add a word only if a plain choice always works.

## List

| Avoid | Use instead | Note |
| --- | --- | --- |
| utilize | use | Same meaning, fewer letters. |
| utilization | use | The noun form. |
| employ | use | Say "use" for tools and methods. |
| prior to | before | |
| subsequent to | after | |
| subsequently | then, later | |
| in order to | to | Cut the first three words. |
| so as to | to | Cut the first three words. |
| commence | start | |
| initiate | start | |
| undertake | do, start | |
| terminate | stop, end | |
| ensure | make sure | |
| approximately | about | Give the number when you know it. |
| facilitate | help, make easier | |
| assist | help | |
| assistance | help | |
| endeavor | try | |
| attempt | try | |
| demonstrate | show | |
| indicate | show, say | |
| require | need | |
| obtain | get | |
| purchase | buy | |
| sufficient | enough | |
| additional | more, extra | |
| numerous | many | |
| modify | change | |
| locate | find | |
| ascertain | find out | |
| comply | follow | Follow a rule or a step. |
| furnish | give | |
| expedite | speed up | |
| disseminate | share, send out | |
| peruse | read | |
| remainder | rest | |
| proceed | go on, continue | |
| reside | live | |
| optimum | best | |
| methodology | method | |
| magnitude | size | |
| whilst | while | |
| nevertheless | but, still | |
| furthermore | also | Often you can cut it. |
| moreover | also | Often you can cut it. |
| aforementioned | this, that, the | Name the thing again. |
| regarding | about | |
| in the event that | if | |
| due to the fact that | because | |
| despite the fact that | although | |
| at this point in time | now | |
| in the near future | soon | Give a date or a time when you know it. |
| a number of | some, several | |
| the majority of | most | |
| with regard to | about | |
| in accordance with | under, following | |
| for the purpose of | for, to | |
| has the ability to | can | |
| in conjunction with | with | |
| in excess of | more than | |
| as a result of | because of | |
| on a daily basis | daily | |
| until such time as | until | |
