"""Canonical effects taxonomy with pharmacology-grounded descriptions.

Defines 51 canonical effects across three categories (positive, negative, medical),
each with receptor pathway information and synonym mappings for normalizing
messy effect names from various data sources.
"""
import json
import sqlite3
from typing import List, Dict, Any

CANONICAL_EFFECTS: List[Dict[str, Any]] = [
    # =========================================================================
    # POSITIVE EFFECTS (20)
    # =========================================================================
    {
        "name": "relaxed",
        "category": "positive",
        "description": "Full-body tension relief mediated by CB1 activation in the central "
                       "amygdala and GABAergic interneurons, reducing sympathetic nervous "
                       "system output.",
        "synonyms": ["relaxing", "chill", "chilled", "mellow", "calm-body", "soothing"],
        "receptor_pathway": "CB1, GABA-A",
    },
    {
        "name": "euphoric",
        "category": "positive",
        "description": "Intense well-being and pleasure driven by CB1-mediated dopamine "
                       "release in the mesolimbic pathway (nucleus accumbens and VTA).",
        "synonyms": ["euphoria", "blissful", "bliss", "elated"],
        "receptor_pathway": "CB1, dopamine D2",
    },
    {
        "name": "happy",
        "category": "positive",
        "description": "Elevated mood linked to serotonergic modulation via 5-HT1A partial "
                       "agonism and CB1-mediated anandamide elevation in prefrontal cortex.",
        "synonyms": ["cheerful", "joyful", "good-mood", "positive-mood"],
        "receptor_pathway": "CB1, 5-HT1A",
    },
    {
        "name": "creative",
        "category": "positive",
        "description": "Enhanced divergent thinking associated with increased cerebral blood "
                       "flow to the frontal lobe and CB1-mediated disinhibition of associative "
                       "networks.",
        "synonyms": ["creativity", "inspired", "imaginative", "artistic"],
        "receptor_pathway": "CB1, dopamine D2",
    },
    {
        "name": "energetic",
        "category": "positive",
        "description": "Increased physical and mental vitality through noradrenergic activation "
                       "and TRPV1-mediated peripheral stimulation, often associated with "
                       "pinene and limonene terpene profiles.",
        "synonyms": ["energy", "energized", "invigorated", "stimulated", "active"],
        "receptor_pathway": "CB1, TRPV1, norepinephrine",
    },
    {
        "name": "focused",
        "category": "positive",
        "description": "Improved concentration and attentional control via modulation of "
                       "prefrontal cortex dopamine and norepinephrine signaling, with "
                       "alpha-pinene terpene contribution to acetylcholinesterase inhibition.",
        "synonyms": ["focus", "attentive", "concentrated", "alert", "clear-headed"],
        "receptor_pathway": "CB1, dopamine D1, AChE",
    },
    {
        "name": "uplifted",
        "category": "positive",
        "description": "Mood elevation and optimism through serotonin and dopamine pathway "
                       "modulation, often associated with limonene-dominant terpene profiles.",
        "synonyms": ["uplifting", "elevated", "lifted", "bright"],
        "receptor_pathway": "CB1, 5-HT1A, dopamine",
    },
    {
        "name": "giggly",
        "category": "positive",
        "description": "Lowered laughter threshold through CB1-mediated disinhibition of "
                       "social processing circuits in the temporal and prefrontal cortex.",
        "synonyms": ["laughing", "laughy", "funny", "giddy"],
        "receptor_pathway": "CB1, dopamine D2",
    },
    {
        "name": "talkative",
        "category": "positive",
        "description": "Enhanced social communication via CB1 modulation of dopaminergic "
                       "pathways in Broca's area and reduced social anxiety through "
                       "amygdala suppression.",
        "synonyms": ["chatty", "social", "sociable", "verbose"],
        "receptor_pathway": "CB1, dopamine, GABA-A",
    },
    {
        "name": "tingly",
        "category": "positive",
        "description": "Peripheral sensory stimulation from TRPV1 and CB1 receptor activation "
                       "on sensory neurons, producing pleasant paresthesia throughout the body.",
        "synonyms": ["tingling", "pins-and-needles", "buzzy", "vibrating"],
        "receptor_pathway": "TRPV1, CB1, CB2",
    },
    {
        "name": "aroused",
        "category": "positive",
        "description": "Heightened sexual arousal through CB1-mediated vasodilation, oxytocin "
                       "release, and enhanced tactile sensitivity via peripheral CB1/TRPV1 "
                       "activation.",
        "synonyms": ["horny", "turned-on", "sensual", "lustful"],
        "receptor_pathway": "CB1, TRPV1, oxytocin",
    },
    {
        "name": "hungry",
        "category": "positive",
        "description": "Appetite stimulation (the 'munchies') driven by CB1 activation in "
                       "the hypothalamus, enhanced olfactory sensitivity, and ghrelin release "
                       "from the stomach.",
        "synonyms": ["munchies", "appetite", "snacky", "famished"],
        "receptor_pathway": "CB1, ghrelin, hypothalamic",
    },
    {
        "name": "sleepy",
        "category": "positive",
        "description": "Sedation and drowsiness mediated by CBN/THC synergy on CB1 receptors, "
                       "myrcene terpene potentiation, and GABAergic enhancement promoting "
                       "sleep onset.",
        "synonyms": ["drowsy", "sedated", "tired", "sleep-inducing", "knocked-out"],
        "receptor_pathway": "CB1, GABA-A, adenosine",
    },
    {
        "name": "calm",
        "category": "positive",
        "description": "Mental tranquility and reduced racing thoughts via CB1-mediated "
                       "suppression of default mode network overactivity and anxiolytic "
                       "5-HT1A partial agonism.",
        "synonyms": ["calming", "peaceful", "serene", "tranquil", "zen"],
        "receptor_pathway": "CB1, 5-HT1A, GABA-A",
    },
    {
        "name": "motivated",
        "category": "positive",
        "description": "Enhanced goal-directed behavior through low-dose CB1 modulation of "
                       "dopamine release in the prefrontal cortex and nucleus accumbens, "
                       "increasing reward anticipation.",
        "synonyms": ["driven", "ambitious", "productive", "determined"],
        "receptor_pathway": "CB1, dopamine D1, D2",
    },
    {
        "name": "meditative",
        "category": "positive",
        "description": "Enhanced introspective and mindful states through CB1-mediated "
                       "default mode network modulation and 5-HT1A-mediated reduction of "
                       "mental chatter.",
        "synonyms": ["contemplative", "introspective", "mindful", "reflective"],
        "receptor_pathway": "CB1, 5-HT1A",
    },
    {
        "name": "body-high",
        "category": "positive",
        "description": "Diffuse physical euphoria from CB1 and CB2 activation on peripheral "
                       "sensory neurons combined with TRPV1-mediated warmth and muscle relaxation.",
        "synonyms": ["body-buzz", "body-euphoria", "physical-high", "body-stone"],
        "receptor_pathway": "CB1, CB2, TRPV1",
    },
    {
        "name": "head-high",
        "category": "positive",
        "description": "Cerebral psychoactive effects predominantly from CB1 activation in "
                       "cortical regions, producing altered perception and thought patterns "
                       "without heavy body sedation.",
        "synonyms": ["cerebral", "heady", "mental-high", "brain-buzz"],
        "receptor_pathway": "CB1, dopamine, serotonin",
    },
    {
        "name": "spacey",
        "category": "positive",
        "description": "Mild dissociation and dreamlike cognition from CB1-mediated disruption "
                       "of hippocampal theta rhythms and altered temporal perception in the "
                       "prefrontal cortex.",
        "synonyms": ["spaced-out", "floaty", "dreamy", "zoned-out", "otherworldly"],
        "receptor_pathway": "CB1, hippocampal",
    },
    {
        "name": "mouth-watering",
        "category": "positive",
        "description": "Increased salivation and taste enhancement driven by CB1 activation "
                       "in gustatory cortex and parasympathetic stimulation of salivary glands, "
                       "distinct from appetite stimulation.",
        "synonyms": ["salivating", "taste-enhanced", "flavorful"],
        "receptor_pathway": "CB1, parasympathetic",
    },

    # =========================================================================
    # NEGATIVE EFFECTS (12)
    # =========================================================================
    {
        "name": "dry-mouth",
        "category": "negative",
        "description": "Reduced salivation (xerostomia) caused by CB1 and CB2 receptor "
                       "activation in submandibular gland parasympathetic ganglia, inhibiting "
                       "acetylcholine-mediated saliva production.",
        "synonyms": ["cottonmouth", "thirsty", "dry-throat", "parched"],
        "receptor_pathway": "CB1, CB2, muscarinic",
    },
    {
        "name": "dry-eyes",
        "category": "negative",
        "description": "Decreased tear production from CB1-mediated inhibition of lacrimal "
                       "gland secretion and reduced aqueous humor outflow causing intraocular "
                       "pressure changes.",
        "synonyms": ["red-eyes", "bloodshot", "itchy-eyes", "irritated-eyes"],
        "receptor_pathway": "CB1, muscarinic",
    },
    {
        "name": "dizzy",
        "category": "negative",
        "description": "Vestibular disruption and orthostatic hypotension from CB1-mediated "
                       "vasodilation and reduced cerebellar coordination, particularly at "
                       "higher doses.",
        "synonyms": ["dizziness", "lightheaded", "vertigo", "unsteady", "woozy"],
        "receptor_pathway": "CB1, cardiovascular",
    },
    {
        "name": "paranoid",
        "category": "negative",
        "description": "Excessive threat detection from CB1 overstimulation of the amygdala "
                       "and hippocampus, overwhelming endocannabinoid buffering and triggering "
                       "hypervigilant pattern matching.",
        "synonyms": ["paranoia", "suspicious", "mistrustful", "on-edge"],
        "receptor_pathway": "CB1, amygdala, norepinephrine",
    },
    {
        "name": "anxious",
        "category": "negative",
        "description": "Heightened anxiety from biphasic CB1 response at high doses -- "
                       "excessive amygdala activation, cortisol release, and disruption of "
                       "the HPA axis stress response.",
        "synonyms": ["anxiety", "nervous", "worried", "panicky", "uneasy", "restless"],
        "receptor_pathway": "CB1, HPA axis, norepinephrine",
    },
    {
        "name": "headache",
        "category": "negative",
        "description": "Cephalgia potentially from rebound vasodilation, dehydration, or "
                       "terpene sensitivity, with CB1-mediated changes in trigeminal nerve "
                       "signaling.",
        "synonyms": ["head-pain", "migraine-like", "head-pressure"],
        "receptor_pathway": "CB1, TRPV1, trigeminal",
    },
    {
        "name": "nauseous",
        "category": "negative",
        "description": "Dose-dependent emetic response from CB1 activation in the area "
                       "postrema (chemoreceptor trigger zone) and vagal afferents, "
                       "paradoxically opposite to antiemetic effects at lower doses.",
        "synonyms": ["nausea", "queasy", "sick", "stomach-upset", "vomiting"],
        "receptor_pathway": "CB1, 5-HT3, vagal",
    },
    {
        "name": "rapid-heartbeat",
        "category": "negative",
        "description": "Tachycardia from CB1-mediated sympathetic activation and vagal "
                       "inhibition, increasing heart rate by 20-50% acutely, particularly "
                       "in naive users.",
        "synonyms": ["tachycardia", "racing-heart", "heart-pounding", "palpitations"],
        "receptor_pathway": "CB1, sympathetic, vagal",
    },
    {
        "name": "couch-lock",
        "category": "negative",
        "description": "Extreme sedation and physical immobility from high-dose CB1 "
                       "activation combined with myrcene terpene potentiation of GABAergic "
                       "inhibition in motor circuits.",
        "synonyms": ["couch-locked", "immobile", "stuck", "body-lock", "glued"],
        "receptor_pathway": "CB1, GABA-A, motor cortex",
    },
    {
        "name": "disoriented",
        "category": "negative",
        "description": "Spatial and temporal confusion from CB1-mediated disruption of "
                       "hippocampal place cells and entorhinal grid cells, impairing "
                       "navigation and time perception.",
        "synonyms": ["confused", "disorientation", "lost", "bewildered"],
        "receptor_pathway": "CB1, hippocampal",
    },
    {
        "name": "fatigued",
        "category": "negative",
        "description": "Post-use exhaustion from adenosine accumulation following CB1-mediated "
                       "dopamine depletion and disrupted sleep architecture during cannabis-"
                       "induced sleep.",
        "synonyms": ["fatigue", "lethargic", "drained", "wiped-out", "burnt-out"],
        "receptor_pathway": "CB1, adenosine, dopamine",
    },
    {
        "name": "irritable",
        "category": "negative",
        "description": "Increased irritability from endocannabinoid system rebound after "
                       "acute use, with reduced GABAergic tone and heightened amygdala "
                       "reactivity to negative stimuli.",
        "synonyms": ["irritability", "cranky", "agitated", "short-tempered", "grumpy"],
        "receptor_pathway": "CB1, GABA-A, amygdala",
    },

    # =========================================================================
    # MEDICAL EFFECTS (19)
    # =========================================================================
    {
        "name": "pain",
        "category": "medical",
        "description": "Analgesic relief through CB1/CB2-mediated inhibition of nociceptive "
                       "signaling in dorsal horn, descending pain modulation, and peripheral "
                       "anti-inflammatory action via TRPV1 desensitization.",
        "synonyms": ["pain-relief", "analgesic", "anti-pain", "chronic-pain", "pain-management"],
        "receptor_pathway": "CB1, CB2, TRPV1, mu-opioid",
    },
    {
        "name": "stress",
        "category": "medical",
        "description": "Stress reduction through CB1-mediated suppression of HPA axis "
                       "cortisol output and amygdala fear response, with anxiolytic "
                       "contribution from 5-HT1A partial agonism.",
        "synonyms": ["stress-relief", "anti-stress", "destress", "tension-relief"],
        "receptor_pathway": "CB1, 5-HT1A, HPA axis",
    },
    {
        "name": "anxiety",
        "category": "medical",
        "description": "Anxiolytic effects at low-moderate doses via CB1-mediated "
                       "enhancement of GABAergic inhibition in basolateral amygdala and "
                       "CBD-mediated 5-HT1A partial agonism.",
        "synonyms": ["anxiety-relief", "anti-anxiety", "anxiolytic", "calm-nerves"],
        "receptor_pathway": "CB1, 5-HT1A, GABA-A",
    },
    {
        "name": "depression",
        "category": "medical",
        "description": "Antidepressant-like effects from rapid CB1-mediated enhancement of "
                       "serotonergic and dopaminergic neurotransmission, with endocannabinoid "
                       "system restoration of hedonic tone.",
        "synonyms": ["depression-relief", "antidepressant", "mood-disorder", "low-mood"],
        "receptor_pathway": "CB1, 5-HT1A, dopamine",
    },
    {
        "name": "insomnia",
        "category": "medical",
        "description": "Sleep-promoting effects through CBN/THC CB1 agonism increasing "
                       "adenosine signaling, myrcene-mediated GABA-A potentiation, and "
                       "reduction of REM sleep latency.",
        "synonyms": ["sleep-aid", "insomnia-relief", "sleep-disorder", "sleeplessness"],
        "receptor_pathway": "CB1, GABA-A, adenosine",
    },
    {
        "name": "nausea-relief",
        "category": "medical",
        "description": "Antiemetic action through CB1 agonism in the dorsal vagal complex "
                       "and 5-HT3 receptor antagonism, particularly effective for "
                       "chemotherapy-induced nausea (CINV).",
        "synonyms": ["anti-nausea", "antiemetic", "anti-vomiting", "stomach-settling"],
        "receptor_pathway": "CB1, 5-HT3, vagal",
    },
    {
        "name": "appetite-loss",
        "category": "medical",
        "description": "Appetite stimulation for cachexia and wasting syndromes through "
                       "CB1-mediated ghrelin release and hypothalamic feeding circuit "
                       "activation, countering appetite loss.",
        "synonyms": ["appetite-stimulant", "cachexia", "wasting", "anorexia-treatment"],
        "receptor_pathway": "CB1, ghrelin, hypothalamic",
    },
    {
        "name": "inflammation",
        "category": "medical",
        "description": "Anti-inflammatory action through CB2-mediated immune cell modulation, "
                       "inhibition of NF-kB pro-inflammatory signaling, and reduction of "
                       "TNF-alpha, IL-6, and other cytokines.",
        "synonyms": ["anti-inflammatory", "inflammation-relief", "swelling", "inflammatory"],
        "receptor_pathway": "CB2, PPARgamma, NF-kB",
    },
    {
        "name": "muscle-spasms",
        "category": "medical",
        "description": "Antispasmodic relief through CB1-mediated inhibition of excitatory "
                       "neurotransmission at neuromuscular junctions and central motor "
                       "circuit regulation, relevant to MS and spasticity.",
        "synonyms": ["spasticity", "muscle-relaxant", "cramps", "spasm-relief", "muscle-tension"],
        "receptor_pathway": "CB1, GABA-A, glycine",
    },
    {
        "name": "seizures",
        "category": "medical",
        "description": "Anticonvulsant effects primarily from CBD-mediated GPR55 antagonism, "
                       "TRPV1 desensitization, and enhanced adenosine signaling reducing "
                       "neuronal hyperexcitability (FDA-approved for Dravet/Lennox-Gastaut).",
        "synonyms": ["epilepsy", "anticonvulsant", "seizure-relief", "convulsions"],
        "receptor_pathway": "GPR55, TRPV1, adenosine, 5-HT1A",
    },
    {
        "name": "ptsd",
        "category": "medical",
        "description": "PTSD symptom management through CB1-mediated fear extinction in the "
                       "amygdala-prefrontal circuit, disruption of traumatic memory "
                       "reconsolidation, and nightmare suppression.",
        "synonyms": ["trauma", "ptsd-relief", "post-traumatic", "flashbacks"],
        "receptor_pathway": "CB1, amygdala, hippocampal",
    },
    {
        "name": "migraines",
        "category": "medical",
        "description": "Migraine relief through CB1-mediated inhibition of trigeminal "
                       "nociception, serotonergic modulation of cortical spreading depression, "
                       "and TRPV1-mediated CGRP release reduction.",
        "synonyms": ["migraine-relief", "headache-relief", "cluster-headaches"],
        "receptor_pathway": "CB1, TRPV1, 5-HT1A, trigeminal",
    },
    {
        "name": "fatigue-medical",
        "category": "medical",
        "description": "Management of chronic fatigue through low-dose CB1-mediated "
                       "dopaminergic stimulation, improved sleep quality, and reduced "
                       "neuroinflammation contributing to central fatigue.",
        "synonyms": ["chronic-fatigue", "cfs", "fatigue-relief", "energy-restoration"],
        "receptor_pathway": "CB1, dopamine, adenosine",
    },
    {
        "name": "eye-pressure",
        "category": "medical",
        "description": "Intraocular pressure reduction through CB1-mediated increase in "
                       "aqueous humor outflow and decreased production via ciliary body "
                       "receptor activation, relevant to glaucoma treatment.",
        "synonyms": ["glaucoma", "iop-reduction", "intraocular-pressure", "eye-pressure-relief"],
        "receptor_pathway": "CB1, ciliary body",
    },
    {
        "name": "arthritis",
        "category": "medical",
        "description": "Joint pain and inflammation relief through CB2-mediated suppression "
                       "of synovial inflammation, CB1 analgesia in joint nociceptors, and "
                       "TRPV1 desensitization in arthritic joints.",
        "synonyms": ["joint-pain", "rheumatoid", "osteoarthritis", "joint-inflammation"],
        "receptor_pathway": "CB1, CB2, TRPV1, PPARgamma",
    },
    {
        "name": "fibromyalgia",
        "category": "medical",
        "description": "Central sensitization management through endocannabinoid deficiency "
                       "correction, CB1-mediated descending pain inhibition, and improved "
                       "sleep quality addressing fibromyalgia's multifactorial pathology.",
        "synonyms": ["fibro", "fibromyalgia-relief", "central-sensitization"],
        "receptor_pathway": "CB1, CB2, 5-HT1A, TRPV1",
    },
    {
        "name": "adhd",
        "category": "medical",
        "description": "Attention and impulse regulation through CB1-mediated modulation of "
                       "prefrontal dopamine signaling, with potential normalization of "
                       "dopamine transporter function in ADHD patients.",
        "synonyms": ["add", "attention-deficit", "hyperactivity", "focus-disorder"],
        "receptor_pathway": "CB1, dopamine D1, D2, norepinephrine",
    },
    {
        "name": "gastrointestinal",
        "category": "medical",
        "description": "GI symptom relief through CB1/CB2 modulation of enteric nervous "
                       "system motility, reduction of intestinal inflammation via CB2, "
                       "and visceral pain suppression relevant to IBS and Crohn's disease.",
        "synonyms": ["ibs", "crohns", "gi-relief", "digestive", "stomach-issues", "colitis"],
        "receptor_pathway": "CB1, CB2, TRPV1, enteric",
    },
    {
        "name": "bipolar",
        "category": "medical",
        "description": "Mood stabilization through endocannabinoid system regulation of "
                       "glutamate/GABA balance, CB1-mediated dampening of manic dopamine "
                       "surges, and neuroprotective effects during mood episodes.",
        "synonyms": ["bipolar-disorder", "mood-stabilizer", "mania", "manic-depression"],
        "receptor_pathway": "CB1, GABA-A, glutamate, dopamine",
    },
]


def seed_canonical_effects(conn: sqlite3.Connection) -> int:
    """Insert all canonical effects into the database.

    Uses INSERT OR IGNORE to ensure idempotency -- running this multiple
    times will not create duplicate rows.

    Args:
        conn: SQLite database connection with canonical_effects table.

    Returns:
        Number of effects that were actually inserted (not already present).
    """
    inserted = 0
    for effect in CANONICAL_EFFECTS:
        cursor = conn.execute(
            """INSERT OR IGNORE INTO canonical_effects
               (name, category, description, synonyms, receptor_pathway)
               VALUES (?, ?, ?, ?, ?)""",
            (
                effect["name"],
                effect["category"],
                effect["description"],
                json.dumps(effect["synonyms"]),
                effect["receptor_pathway"],
            ),
        )
        inserted += cursor.rowcount
    conn.commit()
    return inserted
