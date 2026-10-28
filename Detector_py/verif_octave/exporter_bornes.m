%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% exporter_bornes : reference pour l'etape 1 du portage B (lecture d'un morceau)
%    Outillage de verification, ecrit par Claude (Anthropic) ; ce n'est pas du code du portage.
%    Les calculs de bornes sont recopies de A* (run_bahia/DetectorNBHF_todos_passe_bande.m) :
%    audioinfo, N, t_entrada, t_salida, inicioN, finN, floor(max(.,1)), floor(min(.,tamano_total)).
%
%    inputs  : tous les .wav de jeu_equivalence/wav/
%    outputs : sorties/infos.csv   (fm, tamano_total, nbCanales, N par fichier)
%              sorties/bornes.csv  (pour chaque morceau et chaque canal : bornes lues
%                                   et empreintes exactes des echantillons)
%
%    Les empreintes (somme, somme des valeurs absolues) sont exactes quel que soit l'ordre
%    de sommation : en PCM_16, chaque echantillon vaut k/32768, et toutes les sommes
%    partielles restent representables exactement en double. Python doit donc retrouver
%    les memes valeurs au bit pres.
%
%    Lancer : octave --no-gui verif_octave/exporter_bornes.m   (depuis Detector_py/)
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

clear

ici = fileparts(mfilename('fullpath'));
dossier_wav = fullfile(ici, '..', '..', 'jeu_equivalence', 'wav');
dossier_sortie = fullfile(ici, 'sorties');

% identique a A*
t_trozo=29.99;

fichiers = dir(fullfile(dossier_wav, '*.wav'));

fid_infos = fopen(fullfile(dossier_sortie, 'infos.csv'), 'w');
fprintf(fid_infos, 'fichier;fm;tamano_total;nbCanales;N\n');
fid_bornes = fopen(fullfile(dossier_sortie, 'bornes.csv'), 'w');
fprintf(fid_bornes, 'fichier;i;inicio;fin;canal;n;somme;somme_abs;minimum;maximum;x1;x2;x3;xn_2;xn_1;xn\n');

for k=1:numel(fichiers)
  nom = fichiers(k).name;
  ArchivoSonido = fullfile(dossier_wav, nom);

  informations = audioinfo(ArchivoSonido);
  fm = informations.SampleRate;
  tamano_total = informations.TotalSamples;
  nbCanales = informations.NumChannels;

  tiempo_total_archivo_secundos=tamano_total/fm;
  N=floor(tiempo_total_archivo_secundos/t_trozo)+1;
  fprintf(fid_infos, '%s;%d;%d;%d;%d\n', nom, fm, tamano_total, nbCanales, N);

  for i=1:1:N
    t_entrada=(i-1)*t_trozo;
    t_salida=t_entrada+t_trozo;
    inicioN = t_entrada * fm;
    finN = t_salida * fm;
    inicio = floor(max(inicioN,1));
    fin = floor(min(finN,tamano_total));

    extrait=audioread(ArchivoSonido,[inicio fin]);

    for c=1:nbCanales
      x = extrait(:,c);
      n = length(x);
      fprintf(fid_bornes, '%s;%d;%d;%d;%d;%d;%.17g;%.17g;%.17g;%.17g;%.17g;%.17g;%.17g;%.17g;%.17g;%.17g\n', ...
              nom, i, inicio, fin, c, n, sum(x), sum(abs(x)), min(x), max(x), ...
              x(1), x(2), x(3), x(n-2), x(n-1), x(n));
    end
  end
  printf('%2d/%d  %s  (%d morceaux)\n', k, numel(fichiers), nom, N);
  fflush(stdout);
end

fclose(fid_infos);
fclose(fid_bornes);
