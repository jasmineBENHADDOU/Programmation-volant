 État d'Avancement du Projet

L'objectif de cette période était de valider la chaîne d'acquisition acoustique haute fréquence (ultrasons) entre le PC (émetteur) et le Raspberry Pi (récepteur intégré au volant) pour le projet Dragonfly V2.

Validation Matérielle : Le microphone numérique MEMS SPH0645 est correctement câblé en I2S sur le Raspberry Pi. Le script de test brut confirme la bonne réception des données sur le canal de capture par défaut (Canal 0) avec un taux d'échantillonnage de 48 kHz.

Pivot Logiciel (Choix de la FFT) : Après des tests infructueux avec un filtre adapté (corrélation croisée), l'algorithme a été réorienté avec succès vers une Analyse Spectrale par FFT (Transformée de Fourier Rapide).

Génération du Signal : Les barrières liées aux pilotes audio Windows ont été contournées en générant directement un fichier stationnaire chirp_test.wav au format 16-bit INT16, garantissant une émission stable depuis le PC.

 Conclusions des Tests et Résultats 

Les essais expérimentaux menés en environnement réel ont permis de tirer des conclusions majeures pour la suite du développement :

1. Pourquoi l'approche par Corrélation a échoué
Le premier script cherchait une correspondance géométrique temporelle parfaite du signal. Les haut-parleurs grand public introduisent des micro-déformations de phase et une atténuation sévère au-delà de 15 kHz. Mathématiquement, le score de ressemblance s'effondrait, bloquant le pic de détection à 0.00.

2. Pourquoi l'approche par FFT est un succès
La FFT convertit le signal du domaine temporel vers le domaine fréquentiel. Au lieu de chercher la forme exacte de l'onde, elle mesure simplement l'énergie brute présente dans une bande de fréquences définie.

Résultat du test : Dès que le PC émet dans la plage 16 kHz - 19 kHz, l'énergie lue par le Raspberry Pi bondit instantanément (dépassant notre seuil critique), validant la détection.

3. Immunité aux bruits ambiants de la pièce
Les tests confirment que l'algorithme FFT est totalement insensible aux bruits du quotidien (voix humaine, clics des boutons du volant, bruits de frappe sur un clavier). Ces bruits se situent tous en dessous de 8 kHz. La "fenêtre de surveillance" logicielle configurée entre 16 kHz et 19 kHz fait office de barrière absolue.
