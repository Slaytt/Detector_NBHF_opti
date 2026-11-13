%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% export_bounds : reference for step 1 of port B (reading a chunk)
%    Verification tooling, written by Claude (Anthropic); not part of the port itself.
%    The bound computations are copied from A* (run_bahia/DetectorNBHF_todos_passe_bande.m):
%    audioinfo, N, t_entrada, t_salida, inicioN, finN, floor(max(.,1)), floor(min(.,tamano_total)).
%    Variable names and CSV columns keep A's names on purpose.
%
%    inputs  : all .wav files in jeu_equivalence/wav/
%    outputs : outputs/infos.csv   (fm, tamano_total, nbCanales, N per file)
%              outputs/bounds.csv  (for each chunk and each channel: bounds read
%                                   and exact fingerprints of the samples)
%
%    The fingerprints (sum, sum of absolute values) are exact whatever the summation
%    order: in PCM_16 every sample is k/32768, and all partial sums stay exactly
%    representable in double. Python must therefore find the same values bit for bit.
%
%    Run: octave --no-gui research/octave_check/export_bounds.m   (from the repo root)
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

clear

here = fileparts(mfilename('fullpath'));
wav_dir = fullfile(here, '..', 'jeu_equivalence', 'wav');
out_dir = fullfile(here, 'outputs');

% same as A*
t_trozo=29.99;

files = dir(fullfile(wav_dir, '*.wav'));

fid_infos = fopen(fullfile(out_dir, 'infos.csv'), 'w');
fprintf(fid_infos, 'fichier;fm;tamano_total;nbCanales;N\n');
fid_bounds = fopen(fullfile(out_dir, 'bounds.csv'), 'w');
fprintf(fid_bounds, 'fichier;i;inicio;fin;canal;n;somme;somme_abs;minimum;maximum;x1;x2;x3;xn_2;xn_1;xn\n');

for k=1:numel(files)
  name = files(k).name;
  ArchivoSonido = fullfile(wav_dir, name);

  informations = audioinfo(ArchivoSonido);
  fm = informations.SampleRate;
  tamano_total = informations.TotalSamples;
  nbCanales = informations.NumChannels;

  tiempo_total_archivo_secundos=tamano_total/fm;
  N=floor(tiempo_total_archivo_secundos/t_trozo)+1;
  fprintf(fid_infos, '%s;%d;%d;%d;%d\n', name, fm, tamano_total, nbCanales, N);

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
      fprintf(fid_bounds, '%s;%d;%d;%d;%d;%d;%.17g;%.17g;%.17g;%.17g;%.17g;%.17g;%.17g;%.17g;%.17g;%.17g\n', ...
              name, i, inicio, fin, c, n, sum(x), sum(abs(x)), min(x), max(x), ...
              x(1), x(2), x(3), x(n-2), x(n-1), x(n));
    end
  end
  printf('%2d/%d  %s  (%d chunks)\n', k, numel(files), name, N);
  fflush(stdout);
end

fclose(fid_infos);
fclose(fid_bounds);
