# import
import mlflow
import mlflow.tensorflow
from tensorflow.keras.preprocessing.image import ImageDataGenerator
from tensorflow.keras.applications import MobileNetV2
from tensorflow.keras.layers import AveragePooling2D
from tensorflow.keras.layers import Dropout
from tensorflow.keras.layers import Flatten
from tensorflow.keras.layers import Dense
from tensorflow.keras.layers import Input
from tensorflow.keras.models import Model
from tensorflow.keras.optimizers import Adam
from tensorflow.keras.applications.mobilenet_v2 import preprocess_input
from tensorflow.keras.preprocessing.image import img_to_array
from tensorflow.keras.preprocessing.image import load_img
from tensorflow.keras.utils import to_categorical
from sklearn.preprocessing import LabelBinarizer
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
from imutils import paths
import matplotlib.pyplot as plt
import numpy as np
import os


# initialize MLFlow
mlflow.set_experiment("Face Mask Detection")
mlflow.tensorflow.autolog()

# initialize the initial learning rate
INIT_LR = 1e-4
EPOCHS = 30  #number of cycle
BS = 32     #batch size



DIRECTORY = r"C:/Users/User/Desktop/Face Mask Detector/data"
CATEGORIES = ["with_mask", "without_mask"]

# grab the list of images in our dataset directory, then initialize the list of data (i.e., images) and class images
print("[INFO] loading images...")

data = []
labels = []

for category in CATEGORIES:
    path = os.path.join(DIRECTORY, category)
    for img in os.listdir(path):
    	img_path = os.path.join(path, img)
    	image = load_img(img_path, target_size=(224, 224))
    	image = img_to_array(image)
    	image = preprocess_input(image)

    	data.append(image)
    	labels.append(category)

# convert image data to Binary
lb = LabelBinarizer()
labels = lb.fit_transform(labels)
labels = to_categorical(labels)

data = np.array(data, dtype="float32")
labels = np.array(labels)

# dividing the data to training and test sample
(trainX, testX, trainY, testY) = train_test_split(data, labels,
	test_size=0.20, stratify=labels, random_state=42)

# construct the training image generator for data augmentation
# creating more images with alteration
augment = ImageDataGenerator(
	rotation_range=20,
	zoom_range=0.15,
	height_shift_range=0.2,
    width_shift_range=0.2,
	shear_range=0.15,
	horizontal_flip=True,
	fill_mode="nearest")


# load the MobileNetV2 network (head fully connected layer sets are left off)
# (CNN)
baseModel = MobileNetV2(weights="imagenet", include_top=False,  #loading the mobilenet with pretrained imagenet weights
	input_tensor=Input(shape=(224, 224, 3)))   #3D format for RGB


# construct the head of the model that will be placed on top of the base model
headModel = baseModel.output
headModel = AveragePooling2D(pool_size=(7, 7))(headModel)
headModel = Flatten(name="flatten")(headModel)
headModel = Dense(128, activation="relu")(headModel)
headModel = Dropout(0.5)(headModel)
headModel = Dense(2, activation="softmax")(headModel)

# place the head FC model on top of the base model (this will become
# the actual model we will train)
model = Model(inputs=baseModel.input, outputs=headModel)

# loop over all layers in the base model and freeze them so that they will
# *not* be updated during the first training process for layer in baseModel.layers:
for layer in baseModel.layers:
	layer.trainable = False

# compile  model
print("Compilation of the MODEL is going on...")
#optimizer adam
optimize = Adam(lr=INIT_LR, decay=INIT_LR / EPOCHS)
model.compile(loss="binary_crossentropy", optimizer=optimize,
			  metrics=["accuracy"])

# train the head of the network
print("Training Head Started...")
with mlflow.start_run():
	H = model.fit(
		augment.flow(trainX, trainY, batch_size=BS),
		steps_per_epoch=len(trainX) // BS,
		validation_data=(testX, testY),
		validation_steps=len(testX) // BS,
		epochs=EPOCHS)

	# Evaluation
	print("Network evaluation...")
	predIdxs = model.predict(testX, batch_size=BS)

	# for each image in the testing set we need to find the index of the
	# label with corresponding largest predicted probability
	predIdxs = np.argmax(predIdxs, axis=1)

	# show a formatted classification report
	print(classification_report(testY.argmax(axis=1), predIdxs,
		target_names=lb.classes_))


	# Log metrics
	mlflow.log_metric("accuracy", H.history["accuracy"][-1])
	mlflow.log_metric("val_accuracy", H.history["val_accuracy"][-1])

	# Save the model
	print("saving mask model...")
	model.save("mask_detector.model", save_format="h5")
	mlflow.tensorflow.log_model(model, "mask_detector_model")



# plot the training loss and accuracy
N = EPOCHS
plt.style.use("ggplot")
plt.figure()
plt.plot(np.arange(0, N), H.history["loss"], label="train_loss")
plt.plot(np.arange(0, N), H.history["val_loss"], label="val_loss")
plt.plot(np.arange(0, N), H.history["accuracy"], label="train_acc")
plt.plot(np.arange(0, N), H.history["val_accuracy"], label="val_acc")
plt.title("Training Loss and Accuracy")
plt.xlabel("Epoch #")
plt.ylabel("Loss/Accuracy")
plt.legend(loc="lower left")
plt.savefig("plot.png")
mlflow.log_artifact("plot.png")