%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% detector_todos : detecta clics de delfines en varios archivos
%    inputs : - archivo 'liste.txt' con el listado de todos los archivos de interés
%             - archivos sonoros situados en /media/patris/Blanc4To/PuertoCisnes2_wav/
%    outputs : - archivos de tipo REs**.txt con las fechas (en secundos) de cada clics, para cada archivo
%	       - un archivo total con el conteo de clics por archivo llamado BilanTot.txt
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%


clear
close all

%  software grafico
graphics_toolkit('gnuplot')

%  medicion del tiempo del calculo
tic();

pkg load signal


%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%%% PARAMETROS
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

%%% Archivos

% Aqui se da el camino de la carpeta de archivos de sonido .wav que se quiere abrir
%Camino = '/media/patris/montreal/Mejillones_2024_09/DonneesHighBlue/';
Camino = '/media/malige/montreal/FitzRoy_2024_11/Polypheme/Convertis/';

% Listado de los archivos (se llama liste.txt y se encuentra en la misma carpeta que este programa)
NombreArchivo = textread('liste_fichiers_extrait.txt','%s');

%%% Parametros de la busqueda de los clicks
% umbral para encontrar los clics
coef_umbral=9
seuil=0.4

% frecuencia del filtro paso alto (Hz)
fcut_low=100000
fcut_high=180000

% frecuencia del clic : bande [f1clic;f2clic]
f1clic=120000
f2clic=140000

% frecuencia de comparaison : bande [f1;f2]
f1=30000
f2=90000

% tiempo minimo entre dos clicks (en s) : es decir no vamos a registrar dos clicks diferentes si el tiempo entre los dos esta menos que t_minimo.
% para delfines costeros : 100 micro_s = 0.1 ms = 1/10000 s
% mais dans notre cas pour ne pas avoir plein de detection des rebonds on a mis t_minimo a 1 ms (dc 2 ms annulés)
t_minimo=1/1000
% t_trozo : tiemo de cada trozo analizado (en s)
t_trozo=29.99;
% umbral para que clics detactados en ambos canales sean igualados (0,4 ms TDOA max)
t_fusion = 5/10000;
%t_detect : seuil en temps pour la détection d'un click
t_detect = 0.0015;



% Archivo general con toda informacion
fileID = fopen('Resultats_passe_bande/BilanTot.txt','w');
fprintf(fileID,'Seuil: %f, coef_umbral %d, frequence coupure basse %d, frequence coupure haute %d,\n', seuil,coef_umbral,fcut_low,fcut_high);
fprintf(fileID,'BP du clic %d - %d, BP de référence %d - %d  \n', f1clic,f2clic,f1,f2);
fprintf(fileID,'  \n');
fprintf(fileID,' Detections : \n');
fprintf(fileID,'Fichier \t canal 1 \t canal 2 \t total \n');

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%  Loop de todos los archivos (k)
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%


for k=1:1:length(NombreArchivo)
%for k=1:2

  %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
  %%%%%%%   Lectura del archivo .wav
  %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%  NombreArchivo{k}
  ArchivoSonido = [Camino NombreArchivo{k}];
  ArchivoResultado1 = ['Resultats_passe_bande/Res_' NombreArchivo{k}(1:25) '_Canal1.txt'];
  ArchivoResultado2 = ['Resultats_passe_bande/Res_' NombreArchivo{k}(1:25) '_Canal2.txt'];
  ArchivoResultado = ['Resultats_passe_bande/Res_' NombreArchivo{k}(1:25) '.txt'];

  %%% Lectura de los parametros del archivo de sonido

  informations = audioinfo(ArchivoSonido);
  fm = informations.SampleRate;
  tamano_total = informations.TotalSamples;
  nbCanales = informations.NumChannels;
  tiempo_total_archivo = informations.Duration;

%{
  ancienne version
  [tamano_total, nbCanales] = wavread(ArchivoSonido, "size");
  [s,fm,dyn] = wavread(ArchivoSonido,[1 10]);
  clear s;
%}


  %% Filtros
%  [butterHF1,butterHF2]=butter(5,fcut_low/(fm/2),'high');
  [butterBHF1,butterBHF2]=butter(5,[fcut_low/(fm/2), fcut_high/(fm/2)]);
%  [butterMF1,butterMF2]=butter(5,[f1/(fm/2),f2/(fm/2)]);

  % tiempo total del archivo (en segundos)
  tiempo_total_archivo_secundos=tamano_total/fm;

  % numero de trozos de t_trozo s
  N=floor(tiempo_total_archivo_secundos/t_trozo)+1;

  %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
  %%% Loop para contar los clicks cada trozo. (i)
  %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
  dates_clicks1=[];
  dates_clicks2=[];
  dates_clicks=[];

  for i=1:1:N

   	t_entrada=(i-1)*t_trozo;
   	t_salida=t_entrada+t_trozo;

	%%% extracto

	inicioN = t_entrada * fm;
   	finN = t_salida * fm;

   	extrait=audioread(ArchivoSonido,[floor(max(inicioN,1)) floor(min(finN,tamano_total))]);

        %%% señal, señal alta frecuencia, señal frecuancia mediana
   	senal1 = extrait(:,1);
	senal1HF=filter(butterBHF1,butterBHF2,senal1);
	umbral1 = std(senal1HF)*coef_umbral;

	%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
	% busqueda de las partes de la senal superiores al umbral
	%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%


   	while (max(senal1HF)>umbral1)
                % Detecta los picos alta frecuencia
       		[x, ix] = max(senal1HF);

                % Descarta los que también tienen energía en frecuencia mediana
                spectre=abs(fft(senal1(max(ix-floor(fm/2000 -1),1):min(ix+floor(fm/2000),length(senal1)))));
       		energieClic = mean(spectre(f1clic/1000:f2clic/1000));
       		energie_bande_passante=mean(spectre(f1/1000:f2/1000));
        	if (energieClic>seuil*energie_bande_passante)
		   dates_clicks1=[dates_clicks1;(i-1)*t_trozo+ix/fm];
          	endif
	        % pone a cero la senal entre el max-t_minimo y el max+t_minimo
       		senal1HF(max(1,ix-floor(t_minimo*fm)):min(length(senal1),ix+floor(t_minimo*fm)))=0;
   	endwhile



	clear senal1;
	clear senal1HF;


        %%% Canal 2
	   if (nbCanales > 1)
	       senal2 = extrait(:,2);
	       senal2HF=filter(butterBHF1,butterBHF2,senal2);
   	       umbral2 = std(senal2HF)*coef_umbral;

%	       n_PeakHF=0;
%               n=0;

	       while (max(senal2HF)>umbral2)
                   % Detecta los picos alta frecuencia
      		   [x, ix] = max(senal2HF);

                   % Descarta los que también tiene energía en frecuencia mediana
                   spectre=abs(fft(senal2(max(ix-floor(fm/2000 -1),1):min(ix+floor(fm/2000),length(senal2)))));
       		   energieClic = mean(spectre(f1clic/1000:f2clic/1000));
       		   energie_bande_passante=mean(spectre(f1/1000:f2/1000));
        	   if (energieClic>seuil*energie_bande_passante)
		      dates_clicks2=[dates_clicks2;(i-1)*t_trozo+ix/fm];
          	   endif
	           % pone a cero la senal entre el max-t_minimo y el max+t_minimo asi cuando calcula de nuevo el max este max desapareció.
       		   senal2HF(max(1,ix-floor(t_minimo*fm)):min(length(senal2),ix+floor(t_minimo*fm)))=0;
	       endwhile


  	       clear senal2;
	       clear senal2HF;

           endif
  endfor % fin de la boucle sur les morceaux (i)

  if (nbCanales > 1) % fusion des clicks détectés sur les deux canaux
       Colonne1=[dates_clicks1;dates_clicks2];
       Colonne2=[ones(length(dates_clicks1),1);2*ones(length (dates_clicks2),1)];
       dates_clicks = [Colonne1 Colonne2];
       dates_clicks = sortrows(dates_clicks);
       n=1;
       while (n<(length(dates_clicks)-1))
             if (abs(dates_clicks(n+1,1)-dates_clicks(n,1))<t_fusion)
                  dates_clicks = [dates_clicks(1:n,:);dates_clicks(n+2:length(dates_clicks),:)] ;
             endif
             n=n+1;
       endwhile

  else
       dates_clicks = [dates_clicks1 ones(length(dates_clicks1),1)];
       dates_clicks = sortrows(dates_clicks);
       dates_clicks2 = dates_clicks1 *0;
  end


  % Affichage du nb de clicks

if length(dates_clicks1)>0
  Detections1 = dates_clicks1(:,(length(dates_clicks)>0));
else
  Detections1=[];
endif

if length(dates_clicks2)>0
  Detections2 = dates_clicks2(:,(length(dates_clicks)>0));
else
  Detections2=[];
endif

if length(dates_clicks)>0
  Detections = dates_clicks(:,(length(dates_clicks)>0));
else
  Detections=[];
endif

  nbclicksCanal1 = length(Detections1);
  nbclicksCanal2 = length(Detections2)*(nbCanales>1);
  nbclicks= length(Detections);



  % ecriture des fichiers de sortie
if (nbCanales > 1)
  dlmwrite(ArchivoResultado1,Detections1);
  dlmwrite(ArchivoResultado2,Detections2);
end
  dlmwrite(ArchivoResultado,dates_clicks,'\t');

  fprintf(fileID,'%s \t %d \t %d \t %d \n', NombreArchivo{k}, nbclicksCanal1,nbclicksCanal2,nbclicks);

endfor % fin de la boucle sur les fichiers (k)
% duracion total de calculo
duracion=toc

fprintf(fileID,'\n');
fprintf(fileID,'Duree totale %f s \n', duracion);

fclose(fileID);
